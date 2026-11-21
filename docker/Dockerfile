FROM frappe/erpnext:v16.55.0

USER frappe
WORKDIR /home/frappe/frappe-bench
COPY --chown=frappe:root . apps/continuity360
RUN sed -i 's/withCredentials: true,/withCredentials: true, transports: ["websocket"],/' apps/frappe/frappe/public/js/frappe/socketio_client.js \
    && test "$(grep -c 'withCredentials: true, transports: \["websocket"\],' apps/frappe/frappe/public/js/frappe/socketio_client.js)" -eq 2 \
    && bench build --app frappe \
    && bench pip install --no-deps -e apps/continuity360 \
    && printf '\ncontinuity360\n' >> sites/apps.txt \
    && bench build --app continuity360 \
    && ln -s ../apps/continuity360/continuity360/public assets/continuity360 \
    && env/bin/python -c 'import json; from pathlib import Path; baked = Path("assets/assets.json"); built = Path("sites/assets/assets.json"); manifest = json.loads(baked.read_text()); manifest.update(json.loads(built.read_text())); baked.write_text(json.dumps(manifest))'

USER root
RUN sed -i 's|proxy_set_header Origin \$proxy_x_forwarded_proto://${FRAPPE_SITE_NAME_HEADER};|proxy_set_header Origin $http_origin;|' /templates/nginx/frappe.conf.template \
    && grep -F 'proxy_set_header Origin $http_origin;' /templates/nginx/frappe.conf.template \
    # Pass the reverse proxy's X-Forwarded-For through unchanged so Frappe sees the real
    # client address (rate limiting, logs). The template otherwise overwrites it with the
    # immediate peer, which is always the reverse proxy.
    && sed -i 's|proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;|proxy_set_header X-Forwarded-For $http_x_forwarded_for;|' /templates/nginx/frappe.conf.template \
    && sed -i 's|proxy_set_header X-Forwarded-For \$remote_addr;|proxy_set_header X-Forwarded-For $http_x_forwarded_for;|' /templates/nginx/frappe.conf.template \
    && test "$(grep -c 'proxy_set_header X-Forwarded-For \$http_x_forwarded_for;' /templates/nginx/frappe.conf.template)" -ge 2
USER frappe
