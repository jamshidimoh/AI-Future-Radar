//go:build windows

package systemproxy

import (
	"encoding/json"
	"fmt"
	"os/exec"
	"regexp"
	"strings"
)

type BackupState struct {
	ProxyEnable   *uint32 `json:"proxy_enable,omitempty"`
	ProxyServer   string `json:"proxy_server,omitempty"`
	ProxyOverride string `json:"proxy_override,omitempty"`
	AutoConfigURL string `json:"auto_config_url,omitempty"`
	WinHTTP       string `json:"winhttp,omitempty"`
}

func run(name string, args ...string) ([]byte, error) {
	out, err := exec.Command(name, args...).CombinedOutput()
	if err != nil {
		return out, fmt.Errorf("%s %v: %w: %s", name, args, err, strings.TrimSpace(string(out)))
	}
	return out, nil
}

func queryValue(name string) (string, bool, error) {
	out, err := exec.Command("reg.exe", "query", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", name).CombinedOutput()
	if err != nil {
		return "", false, nil
	}
	re := regexp.MustCompile(`(?m)^\s*` + regexp.QuoteMeta(name) + `\s+REG_\w+\s+(.+)$`)
	m := re.FindStringSubmatch(string(out))
	if len(m) < 2 {
		return "", false, nil
	}
	return strings.TrimSpace(m[1]), true, nil
}

func Backup() (BackupState, error) {
	var b BackupState
	if v, ok, err := queryValue("ProxyEnable"); err != nil {
		return b, err
	} else if ok {
		var n uint32
		_, _ = fmt.Sscanf(v, "0x%x", &n)
		b.ProxyEnable = &n
	}
	if v, ok, _ := queryValue("ProxyServer"); ok {
		b.ProxyServer = v
	}
	if v, ok, _ := queryValue("ProxyOverride"); ok {
		b.ProxyOverride = v
	}
	if v, ok, _ := queryValue("AutoConfigURL"); ok {
		b.AutoConfigURL = v
	}
	if out, err := exec.Command("netsh", "winhttp", "show", "proxy").CombinedOutput(); err == nil {
		b.WinHTTP = string(out)
	}
	return b, nil
}

func SetAutoConfigURL(url string) error {
	if _, err := run("reg.exe", "add", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", "AutoConfigURL", "/t", "REG_SZ", "/d", url, "/f"); err != nil {
		return err
	}
	if _, err := run("reg.exe", "add", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", "ProxyEnable", "/t", "REG_DWORD", "/d", "0", "/f"); err != nil {
		return err
	}
	return nil
}

func Restore(b BackupState) error {
	if b.AutoConfigURL == "" {
		_, _ = run("reg.exe", "delete", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", "AutoConfigURL", "/f")
	} else if _, err := run("reg.exe", "add", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", "AutoConfigURL", "/t", "REG_SZ", "/d", b.AutoConfigURL, "/f"); err != nil {
		return err
	}
	if b.ProxyServer == "" {
		_, _ = run("reg.exe", "delete", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", "ProxyServer", "/f")
	} else if _, err := run("reg.exe", "add", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", "ProxyServer", "/t", "REG_SZ", "/d", b.ProxyServer, "/f"); err != nil {
		return err
	}
	if b.ProxyOverride == "" {
		_, _ = run("reg.exe", "delete", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", "ProxyOverride", "/f")
	} else if _, err := run("reg.exe", "add", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", "ProxyOverride", "/t", "REG_SZ", "/d", b.ProxyOverride, "/f"); err != nil {
		return err
	}
	if b.ProxyEnable != nil {
		if _, err := run("reg.exe", "add", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", "ProxyEnable", "/t", "REG_DWORD", "/d", fmt.Sprintf("%d", *b.ProxyEnable), "/f"); err != nil {
			return err
		}
	} else {
		_, _ = run("reg.exe", "delete", `HKCUSoftwareMicrosoftWindowsCurrentVersionInternet Settings`, "/v", "ProxyEnable", "/f")
	}
	_, _ = run("netsh", "winhttp", "reset", "proxy")
	return nil
}

func ImportWinHTTPFromIE() error {
	_, err := run("netsh", "winhttp", "import", "proxy", "source=ie")
	return err
}

func IsConfigured() bool {
	v, ok, _ := queryValue("AutoConfigURL")
	return ok && v != ""
}

func Marshal(b BackupState) []byte { x, _ := json.Marshal(b); return x }
