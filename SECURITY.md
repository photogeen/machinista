# Security and deployment

The WebUI intentionally has no login and can modify libraries, install executable
LV2 code and request system operations. Use it only on a trusted local network;
do not port-forward it or expose it on a public interface. Install only plug-ins
you trust. Architecture/metadata checks are not a malware guarantee.

Prepared images document default network/account credentials. SSH is enabled
explicitly rather than being shipped with private developer keys. Keep update
signing keys, WLAN profiles and device state outside Git.

Do not disclose a suspected vulnerability with working credentials, private
samples, ROMs or identifying hardware captures in a public issue. Before the
repository is made public, its owner must configure GitHub private vulnerability
reporting or publish a private contact. No reporting address is invented here.
