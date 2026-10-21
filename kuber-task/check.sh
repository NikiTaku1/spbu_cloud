#!/bin/bash
cd "$(dirname "$0")"
P=0; F=0
ok(){ echo "Y  $1"; P=$((P+1)); }
fail(){ echo "N  $1"; F=$((F+1)); }

R=$(kubectl get deploy backend -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
[ "${R:-0}" -ge 2 ] && ok "Backend реплицирован (готовых подов: $R)" || fail "Backend реплицирован (готовых подов: ${R:-0})"

FR=$(kubectl get deploy frontend -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
[ "${FR:-0}" -ge 1 ] && ok "Frontend запущен" || fail "Frontend запущен"

[ "$(kubectl get svc backend-service -o jsonpath='{.spec.type}' 2>/dev/null)" = "ClusterIP" ] && ok "backend-service: ClusterIP (внутренний порт)" || fail "backend-service: ClusterIP"
[ "$(kubectl get svc frontend-service -o jsonpath='{.spec.type}' 2>/dev/null)" = "LoadBalancer" ] && ok "frontend-service: LoadBalancer" || fail "frontend-service: LoadBalancer"

IP=$(kubectl get svc frontend-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
[ -n "$IP" ] && ok "Frontend имеет внешний IP: $IP" || fail "Frontend имеет внешний IP (запустите minikube tunnel)"

if [ -n "$IP" ]; then
  curl -s -m 5 "http://$IP/" 2>/dev/null | grep -q "Hello from backend" && ok "Frontend пересылает запросы на backend" || fail "Frontend пересылает запросы на backend"
  N=$(for i in $(seq 1 20); do curl -s -m 5 "http://$IP/" 2>/dev/null | grep -o '"pod": "[^"]*"'; done | sort -u | wc -l)
  [ "$N" -ge 2 ] && ok "Балансировка между репликами (разных подов: $N)" || fail "Балансировка между репликами (разных подов: $N)"
else
  fail "Frontend пересылает запросы на backend (нет IP)"
  fail "Балансировка между репликами (нет IP)"
fi

[ -z "$(kubectl get svc backend-service -o jsonpath='{.status.loadBalancer.ingress}' 2>/dev/null)" ] && ok "Backend недоступен снаружи" || fail "Backend недоступен снаружи"

for f in k8s/backend-deployment.yaml k8s/frontend-deployment.yaml k8s/backend-service.yaml k8s/frontend-service.yaml README.md backend/Dockerfile frontend/Dockerfile; do
  [ -f "$f" ] && ok "Файл $f" || fail "Файл $f"
done

echo "----------------------------------------"
echo "Итого: $P пройдено, $F не пройдено"
[ "$F" -eq 0 ]
