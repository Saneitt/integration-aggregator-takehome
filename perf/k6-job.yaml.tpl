apiVersion: batch/v1
kind: Job
metadata:
  name: k6-token-retrieval
  namespace: perf
  labels:
    app.kubernetes.io/name: integration-aggregator-perf
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 600
  activeDeadlineSeconds: 360
  template:
    metadata:
      labels:
        app.kubernetes.io/name: integration-aggregator-perf
    spec:
      restartPolicy: Never
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 12345
        runAsGroup: 12345
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: k6
          image: ${K6_IMAGE}
          imagePullPolicy: IfNotPresent
          command: ["k6", "run", "/scripts/token-retrieval.js"]
          env:
            - name: BASE_URL
              value: http://integration-aggregator.aggregator.svc.cluster.local:8080
            - name: PROVIDER
              value: mock
            - name: TOKEN_USER
              value: perf-user
            - name: POLL_MS
              value: "25"
            - name: MAX_POLLS
              value: "400"
          volumeMounts:
            - name: scripts
              mountPath: /scripts
              readOnly: true
            - name: tmp
              mountPath: /tmp
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          resources:
            requests:
              cpu: 500m
              memory: 256Mi
            limits:
              cpu: "2"
              memory: 1Gi
      volumes:
        - name: scripts
          configMap:
            name: k6-scripts
            defaultMode: 0444
        - name: tmp
          emptyDir:
            sizeLimit: 64Mi
