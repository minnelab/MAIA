Use the install-maia skill to install the full MAIA stack (the verdi component set) on a new server.

Target (keep one):
- existing-ssh-host: install directly on the Ubuntu 24.04 host reachable as `ssh <alias>`
- remote-hypervisor: create a QEMU/KVM VM named <vm-name> on `ssh <alias>` (--hypervisor <alias>),
  <N> vCPU / <N> GB RAM / <N> GB disk

Sizing (for the VM, or the server itself if existing-ssh-host):

- Minimum, tested: 8 vCPU / 16 GB RAM / 150 GB disk. This holds the platform with no users: CPU requests
  were 5.9 of 8, and about 8 GB of RAM was free. 4 vCPU fails, because Keycloak stays Pending on
  Insufficient cpu.
- Recommended for real use: 16 vCPU / 32 GB RAM / 250+ GB on SSD or NVMe, plus whatever each user's
  workspace and GPU jobs need, since they come on top of the platform.
- On a hypervisor, also leave headroom on the host: at least VM RAM + 4 GB, and VM disk + 50 GB free
  (00_preflight.sh checks both).
- Use an SSD. On a rotational disk the database setup times out unless the VM uses
  --disk-cache unsafe, and that option is only acceptable for a disposable test VM.

Cluster: domain <domain>, cluster name <name>, MAIA branch <branch>.
Optional: OpenWebUI LLM endpoints <urls>, with API keys added to secrets.env (never the repo).

Rules:
- Read SKILL.md and references/troubleshooting.md first. Follow the skill's procedure and step table.
- Don't hardcode IPs, users or ports. Read them from `ssh -G <alias>`.
- Show me any ~/.ssh/config entry before adding it.
- Port forwards bind to 127.0.0.1 only, never 0.0.0.0.
- If there's no /dev/kvm, stop and ask. Don't fall back to TCG.
- Check `sudo -n true`. If sudo needs a password, stop and ask. Never pass a become password on the
  command line or write it to a file.
- Secrets live only in ~/.maia-vm/<vm-name>/secrets.env (0600) on this machine. Never put them on the
  server or in the repo, use no_log, and never print secret values in chat.
- Before each phase that changes state on <alias> itself (packages, users, systemd units, firewall),
  show me the commands and wait for a go-ahead. Changes inside a VM you created don't need approval.
- Log every command, where it ran, its timing and a short output excerpt to the skill's RUNBOOK.md.
- If an upstream bug blocks you, work around it in the skill. Propose each upstream fix separately
  and apply none without my approval.
- Don't commit.

Done means 60_verify.sh prints VERIFY OK. Then give me a summary with the URLs, the first-access
admin login (point to where the password is stored, don't print it), timings, and any new issues.