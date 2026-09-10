# Wrapper around the upstream Rakazo app image.
# Why this exists (upstream image alone is not deployable on Railway):
#  1. Railway mounts volumes root-owned; upstream runs as USER node (uid 1000)
#     and gets EACCES on /data (agent homes, artifacts, push tokens, sessions).
#  2. api and worker share DATA_DIR and Railway volumes attach to one service
#     only, so api+worker+web run in one container - which needs a boot
#     sequence, which upstream's single-process CMD does not provide.
FROM ghcr.io/elie222/rakazo/app:v0.1.6
USER root
COPY boot.sh /usr/local/bin/rakazo-boot
RUN chmod 755 /usr/local/bin/rakazo-boot
# No CMD and no Railway start command: Railway discards ENTRYPOINT when a start
# command is set, which would skip the chown. The whole boot lives in boot.sh.
ENTRYPOINT ["/usr/local/bin/rakazo-boot"]
