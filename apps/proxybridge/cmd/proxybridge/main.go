package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/jamshidimoh/proxybridge/internal/app"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:8787", "local dashboard/PAC server address")
	dataDir := flag.String("data", "", "application data directory")
	pacFile := flag.String("pac", "", "path to PAC file to serve")
	systemOn := flag.Bool("system-on", false, "enable Windows system proxy using the local PAC")
	systemOff := flag.Bool("system-off", false, "restore the previous Windows proxy settings")
	dashboard := flag.Bool("dashboard", true, "serve the local dashboard")
	flag.Parse()

	dir := *dataDir
	if dir == "" {
		base, err := os.UserConfigDir()
		if err != nil {
			log.Fatal(err)
		}
		dir = filepath.Join(base, "ProxyBridge")
	}

	cfg, err := app.LoadOrCreateConfig(dir)
	if err != nil {
		log.Fatal(err)
	}
	if *pacFile != "" {
		if err := cfg.SetPACFile(*pacFile); err != nil {
			log.Fatal(err)
		}
	}

	svc := app.NewService(dir, cfg)

	if *systemOn {
		if err := svc.EnableSystemProxy(*addr); err != nil {
			log.Fatal(err)
		}
		fmt.Println("System PAC proxy enabled:", "http://"+*addr+"/proxy.pac")
	}
	if *systemOff {
		if err := svc.DisableSystemProxy(); err != nil {
			log.Fatal(err)
		}
		fmt.Println("Previous system proxy settings restored.")
	}
	if !*dashboard {
		return
	}

	if err := svc.Serve(*addr); err != nil {
		log.Fatal(err)
	}
}
