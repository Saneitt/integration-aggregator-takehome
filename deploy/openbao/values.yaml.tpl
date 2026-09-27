global:
  enabled: true

injector:
  enabled: false

server:
  dev:
    enabled: true
    # V2: server.extraArgs below supplies the real token from a Secret.
    devRootToken: "not-used-see-extraArgs"

  extraSecretEnvironmentVars:
    - envName: BAO_BOOTSTRAP_ROOT_TOKEN
      secretName: openbao-bootstrap
      secretKey: root-token

  # The chart runs this through its shell entrypoint. Keep the token as an env reference.
  extraArgs: "-dev-root-token-id=$BAO_BOOTSTRAP_ROOT_TOKEN -config=/openbao/userconfig/plugins/plugins.hcl"

  extraInitContainers:
    - name: fetch-oauthapp-plugin
      image: ${PLUGIN_FETCH_IMAGE}
      command: ["/bin/sh", "-ec"]
      args:
        - |
          cd /tmp
          asset="openbao-plugin-secrets-oauthapp-${OAUTHAPP_VERSION}-linux-amd64"
          wget -q -O plugin.tar.xz "https://github.com/openbao/openbao-plugin-secrets-oauthapp/releases/download/${OAUTHAPP_VERSION}/$asset.tar.xz"
          printf '%s  plugin.tar.xz\n' "${OAUTHAPP_TARBALL_SHA256}" | sha256sum -c -
          tar -xJf plugin.tar.xz
          cp "$asset" /plugins/oauthapp
          chmod 0755 /plugins/oauthapp
          printf '%s  /plugins/oauthapp\n' "${OAUTHAPP_BINARY_SHA256}" | sha256sum -c -
      volumeMounts:
        - name: plugins
          mountPath: /plugins

  volumes:
    - name: plugins
      emptyDir: {}
    - name: plugin-config
      configMap:
        name: openbao-plugin-config

  volumeMounts:
    - name: plugins
      mountPath: /openbao/plugins
      readOnly: true
    - name: plugin-config
      mountPath: /openbao/userconfig/plugins
      readOnly: true

  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      memory: 256Mi