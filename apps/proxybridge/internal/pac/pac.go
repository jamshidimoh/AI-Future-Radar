package pac

import "strings"

func LooksLikePAC(s string) bool {
	lower := strings.ToLower(s)
	return strings.Contains(lower, "findproxyforurl") && strings.Contains(lower, "return")
}
