#!/bin/sh
# Installs the YouTube feed in this container: the script, a timer that refreshes it every 5 minutes and a small web
# server for /feed.json on port 8080. Run as root from the folder with ytfeed.py.
set -e
install -d -m 755 /opt/ytfeed /etc/ytfeed /var/lib/ytfeed/public
install -m 755 ytfeed.py /opt/ytfeed/ytfeed.py
ln -sf /opt/ytfeed/ytfeed.py /usr/local/bin/ytfeed
[ -f /etc/ytfeed/config.json ] || cat > /etc/ytfeed/config.json <<'EOF'
{
 "days": 10,
 "max_items": 30,
 "order": "recent",
 "per_channel": 0,
 "favorites": [],
 "blocked": []
}
EOF

cat > /etc/systemd/system/ytfeed.service <<'EOF'
[Unit]
Description=YouTube feed for Free My TV (refresh)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/ytfeed/ytfeed.py refresh
EOF

cat > /etc/systemd/system/ytfeed.timer <<'EOF'
[Unit]
Description=Refresh the YouTube feed every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

cat > /etc/systemd/system/ytfeed-web.service <<'EOF'
[Unit]
Description=YouTube feed for Free My TV (serves feed.json on :8080)
After=network.target

[Service]
ExecStart=/usr/bin/python3 -m http.server 8080 --bind 0.0.0.0 --directory /var/lib/ytfeed/public
Restart=always
DynamicUser=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now ytfeed-web.service ytfeed.timer
echo "Installed. Next: put client_secret.json in /etc/ytfeed, then run: ytfeed auth"
