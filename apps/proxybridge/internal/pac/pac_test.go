package pac

import "testing"

func TestLooksLikePAC(t *testing.T) {
	valid := "function FindProxyForURL(url, host) { return 'DIRECT'; }"
	if !LooksLikePAC(valid) {
		t.Fatal("expected valid PAC to be accepted")
	}
	invalid := "function main() { console.log('proxy'); }"
	if LooksLikePAC(invalid) {
		t.Fatal("expected unrelated JavaScript to be rejected")
	}
}
