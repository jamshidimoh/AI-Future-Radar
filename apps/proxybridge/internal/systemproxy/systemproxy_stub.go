//go:build !windows

package systemproxy

type BackupState struct {
	ProxyEnable   *uint32 `json:"proxy_enable,omitempty"`
	ProxyServer   string `json:"proxy_server,omitempty"`
	ProxyOverride string `json:"proxy_override,omitempty"`
	AutoConfigURL string `json:"auto_config_url,omitempty"`
	WinHTTP       string `json:"winhttp,omitempty"`
}

func Backup() (BackupState, error)  { return BackupState{}, nil }
func SetAutoConfigURL(string) error { return nil }
func Restore(BackupState) error     { return nil }
func ImportWinHTTPFromIE() error    { return nil }
func IsConfigured() bool            { return false }
