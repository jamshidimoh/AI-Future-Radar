package app

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"

	"github.com/jamshidimoh/proxybridge/internal/pac"
	"github.com/jamshidimoh/proxybridge/internal/systemproxy"
)

//go:embed assets/index.html
var dashboardHTML string

type Service struct {
	dir    string
	cfg    *Config
	tunMu  sync.Mutex
	tunCmd *exec.Cmd
}

func NewService(dir string, cfg *Config) *Service { return &Service{dir: dir, cfg: cfg} }

func (s *Service) Serve(addr string) error {
	mux := http.NewServeMux()
	mux.HandleFunc("/proxy.pac", s.servePAC)
	mux.HandleFunc("/api/status", s.status)
	mux.HandleFunc("/api/system/on", s.systemOnAPI)
	mux.HandleFunc("/api/system/off", s.systemOffAPI)
	mux.HandleFunc("/api/pac", s.pacAPI)
	mux.HandleFunc("/api/tun/start", s.tunStartAPI)
	mux.HandleFunc("/api/tun/stop", s.tunStopAPI)
	mux.HandleFunc("/api/tun/status", s.tunStatusAPI)
	mux.HandleFunc("/api/tun/config", s.tunConfigAPI)
	mux.HandleFunc("/", s.dashboard)
	fmt.Printf("ProxyBridge dashboard: http://%s/\n", addr)
	fmt.Printf("PAC endpoint: http://%s/proxy.pac\n", addr)
	return http.ListenAndServe(addr, mux)
}

func (s *Service) servePAC(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/x-ns-proxy-autoconfig; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	http.ServeFile(w, r, s.cfg.PACFile)
}

func (s *Service) status(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"os":             runtime.GOOS,
		"pac_file":       s.cfg.PACFile,
		"singbox_config": s.cfg.SingBoxConfig,
		"singbox_path":   s.cfg.SingBoxPath,
		"system_proxy":   systemproxy.IsConfigured(),
	})
}

func (s *Service) systemOnAPI(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST required", http.StatusMethodNotAllowed)
		return
	}
	if err := s.EnableSystemProxy(serverAddrFromRequest(r)); err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	writeJSON(w, map[string]any{"ok": true})
}

func (s *Service) systemOffAPI(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST required", http.StatusMethodNotAllowed)
		return
	}
	if err := s.DisableSystemProxy(); err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	writeJSON(w, map[string]any{"ok": true})
}

func (s *Service) pacAPI(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		b, err := os.ReadFile(s.cfg.PACFile)
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		_, _ = w.Write(b)
	case http.MethodPut:
		b, err := io.ReadAll(io.LimitReader(r.Body, 2<<20))
		if err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		text := string(b)
		if !pac.LooksLikePAC(text) {
			http.Error(w, "invalid PAC: FindProxyForURL(url, host) not found", 400)
			return
		}
		if err := os.WriteFile(s.cfg.PACFile, []byte(text), 0o644); err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		_ = s.cfg.Save(s.dir)
		writeJSON(w, map[string]any{"ok": true})
	default:
		http.Error(w, "GET or PUT required", http.StatusMethodNotAllowed)
	}
}

func (s *Service) dashboard(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = io.WriteString(w, dashboardHTML)
}

func (s *Service) EnableSystemProxy(addr string) error {
	if runtime.GOOS != "windows" {
		return fmt.Errorf("system proxy management is currently implemented for Windows only")
	}
	url := "http://" + strings.TrimPrefix(addr, "http://") + "/proxy.pac"
	backup, err := systemproxy.Backup()
	if err != nil {
		return err
	}
	if err := writeJSONFile(filepath.Join(s.dir, "system-proxy-backup.json"), backup); err != nil {
		return err
	}
	if err := systemproxy.SetAutoConfigURL(url); err != nil {
		return err
	}
	if err := systemproxy.ImportWinHTTPFromIE(); err != nil {
		return err
	}
	s.cfg.LastSystemProxyURL = url
	return s.cfg.Save(s.dir)
}

func (s *Service) DisableSystemProxy() error {
	if runtime.GOOS != "windows" {
		return nil
	}
	bpath := filepath.Join(s.dir, "system-proxy-backup.json")
	b, err := os.ReadFile(bpath)
	if err != nil {
		return err
	}
	var backup systemproxy.BackupState
	if err := json.Unmarshal(b, &backup); err != nil {
		return err
	}
	if err := systemproxy.Restore(backup); err != nil {
		return err
	}
	_ = os.Remove(bpath)
	s.cfg.LastSystemProxyURL = ""
	return s.cfg.Save(s.dir)
}

func serverAddrFromRequest(r *http.Request) string {
	host := r.Host
	if host == "" {
		host = "127.0.0.1:8787"
	}
	return host
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	b, _ := json.Marshal(v)
	_, _ = w.Write(append(b, '\n'))
}

func writeJSONFile(path string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(b, '\n'), 0o600)
}

func (s *Service) SingBoxBinary() string {
	if s.cfg.SingBoxPath != "" {
		return s.cfg.SingBoxPath
	}
	if runtime.GOOS == "windows" {
		return filepath.Join(s.dir, "sing-box", "sing-box.exe")
	}
	return filepath.Join(s.dir, "sing-box", "sing-box")
}

func (s *Service) StartSingBox() error {
	if runtime.GOOS != "windows" {
		return fmt.Errorf("TUN start is currently implemented for Windows only")
	}
	s.tunMu.Lock()
	defer s.tunMu.Unlock()
	if s.tunCmd != nil && s.tunCmd.Process != nil {
		return fmt.Errorf("TUN is already running")
	}
	if s.cfg.SingBoxConfig == "" {
		return fmt.Errorf("set sing-box config path first")
	}
	if _, err := os.Stat(s.cfg.SingBoxConfig); err != nil {
		return fmt.Errorf("sing-box config: %w", err)
	}
	cmd := exec.Command(s.SingBoxBinary(), "run", "-c", s.cfg.SingBoxConfig)
	cmd.Dir = filepath.Dir(s.cfg.SingBoxConfig)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start sing-box: %w", err)
	}
	s.tunCmd = cmd
	return nil
}

func (s *Service) StopSingBox() error {
	s.tunMu.Lock()
	defer s.tunMu.Unlock()
	if s.tunCmd == nil || s.tunCmd.Process == nil {
		return nil
	}
	err := s.tunCmd.Process.Kill()
	s.tunCmd = nil
	return err
}

func (s *Service) TunRunning() bool {
	s.tunMu.Lock()
	defer s.tunMu.Unlock()
	return s.tunCmd != nil && s.tunCmd.Process != nil
}

func (s *Service) tunStartAPI(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST required", http.StatusMethodNotAllowed)
		return
	}
	if err := s.StartSingBox(); err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	writeJSON(w, map[string]any{"ok": true, "running": true})
}

func (s *Service) tunStopAPI(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST required", http.StatusMethodNotAllowed)
		return
	}
	if err := s.StopSingBox(); err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	writeJSON(w, map[string]any{"ok": true, "running": false})
}

func (s *Service) tunConfigAPI(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		writeJSON(w, map[string]any{
			"config": s.cfg.SingBoxConfig,
			"binary": s.SingBoxBinary(),
		})
	case http.MethodPut:
		b, err := io.ReadAll(io.LimitReader(r.Body, 64<<10))
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		path := strings.TrimSpace(string(b))
		if path == "" {
			http.Error(w, "config path is empty", http.StatusBadRequest)
			return
		}
		if _, err := os.Stat(path); err != nil {
			http.Error(w, fmt.Sprintf("config path: %v", err), http.StatusBadRequest)
			return
		}
		s.cfg.SingBoxConfig = path
		if err := s.cfg.Save(s.dir); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		writeJSON(w, map[string]any{"ok": true, "config": path})
	default:
		http.Error(w, "GET or PUT required", http.StatusMethodNotAllowed)
	}
}

func (s *Service) tunStatusAPI(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "GET required", http.StatusMethodNotAllowed)
		return
	}
	writeJSON(w, map[string]any{"running": s.TunRunning(), "config": s.cfg.SingBoxConfig, "binary": s.SingBoxBinary()})
}
