package app

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type Config struct {
	PACFile            string `json:"pac_file"`
	SingBoxConfig      string `json:"singbox_config"`
	SingBoxPath        string `json:"singbox_path"`
	LastSystemProxyURL string `json:"last_system_proxy_url"`
}

func LoadOrCreateConfig(dir string) (*Config, error) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	path := filepath.Join(dir, "config.json")
	cfg := &Config{PACFile: filepath.Join(dir, "proxy.pac")}
	b, err := os.ReadFile(path)
	if err == nil {
		if err := json.Unmarshal(b, cfg); err != nil {
			return nil, fmt.Errorf("invalid config: %w", err)
		}
	} else if !os.IsNotExist(err) {
		return nil, err
	}
	if _, err := os.Stat(cfg.PACFile); os.IsNotExist(err) {
		const directPAC = "function FindProxyForURL(url, host) { return 'DIRECT'; }\n"
		if err := os.WriteFile(cfg.PACFile, []byte(directPAC), 0o644); err != nil {
			return nil, err
		}
	}
	if err := saveConfig(path, cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}

func (c *Config) Save(dir string) error {
	return saveConfig(filepath.Join(dir, "config.json"), c)
}

func saveConfig(path string, cfg *Config) error {
	b, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(b, '\n'), 0o644)
}

func (c *Config) SetPACFile(src string) error {
	b, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	if len(b) == 0 {
		return fmt.Errorf("PAC file is empty")
	}
	if err := os.WriteFile(c.PACFile, b, 0o644); err != nil {
		return err
	}
	return nil
}
