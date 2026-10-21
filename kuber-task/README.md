# Backend–Frontend приложение в Kubernetes

Деплой двух сервисов в Kubernetes (minikube, запуск из WSL).

- **Backend** — HTTP-приложение на Python, слушает внутренний порт 5000 и на каждый запрос возвращает JSON с именем пода, который его обработал. Запущено в **3 репликах**, доступно только внутри кластера (Service типа `ClusterIP`).
- **Frontend** — nginx, слушает порт 80 и проксирует все входящие запросы на backend. Service типа `LoadBalancer` даёт **внешний IP**, доступный вне кластера.

## Архитектура

Клиент отправляет HTTP-запрос на внешний IP-адрес сервиса `frontend-service` (тип `LoadBalancer`, порт 80). Сервис передаёт запрос в под frontend, где работает nginx. Nginx пересылает запрос по DNS-имени `backend-service` на порт 5000.

`backend-service` имеет тип `ClusterIP`, поэтому доступен только внутри кластера. Он распределяет входящие запросы между тремя подами backend. Каждый под обрабатывает запрос и возвращает JSON с собственным именем. Ответ идёт обратно тем же путём: от backend к nginx и затем к клиенту.

## Структура репозитория

```
kuber-task/
├── README.md
├── check.sh                        # автоматическая проверка работоспособности
├── backend/
│   ├── app.py                      # код backend
│   └── Dockerfile
├── frontend/
│   ├── nginx.conf                  # конфиг прокси на backend
│   └── Dockerfile
└── k8s/
    ├── backend-deployment.yaml     # Deployment backend (3 реплики, probes)
    ├── backend-service.yaml        # Service backend (ClusterIP)
    ├── frontend-deployment.yaml    # Deployment frontend
    └── frontend-service.yaml       # Service frontend (LoadBalancer)
```

## Требования

- Windows с WSL2 (Ubuntu)
- Docker (Docker Desktop с включённой WSL-интеграцией либо Docker внутри WSL)
- kubectl и minikube

Установка kubectl и minikube в WSL:

```bash
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install kubectl /usr/local/bin/kubectl

curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

docker version && kubectl version --client && minikube version
```

## Запуск

Все команды выполняются из корня проекта.

```bash
# 1. Запустить кластер
minikube start --driver=docker

# 2. Собрать образы внутри minikube (внешний registry не нужен)
minikube image build -t backend-app:1.0 ./backend
minikube image build -t frontend-app:1.0 ./frontend

# 3. Применить манифесты
kubectl apply -f k8s/

# 4. Дождаться готовности
kubectl rollout status deployment/backend
kubectl rollout status deployment/frontend

# 5. Посмотреть результат
kubectl get pods,svc -o wide
```

Ожидаемо: 3 пода backend и 1 под frontend в статусе `Running`.

## Получение внешнего IP

В minikube сервис типа `LoadBalancer` получает внешний IP через `minikube tunnel`. Запустите его **в отдельном терминале WSL** и не закрывайте:

```bash
minikube tunnel
```

В основном терминале:

```bash
kubectl get svc frontend-service
```

В колонке `EXTERNAL-IP` появится адрес (в драйвере docker обычно `127.0.0.1`).

Запасной вариант без tunnel:

```bash
minikube service frontend-service --url
```

## Тестирование

### Автоматическая проверка

```bash
./check.sh
```

Скрипт выводит `Y` / `N` для каждой проверки: репликация backend, запуск frontend, типы сервисов, внешний IP, проксирование на backend, балансировка, недоступность backend снаружи, наличие файлов.

### Ручная проверка

```bash
# Получить внешний IP
EXTERNAL_IP=$(kubectl get svc frontend-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo $EXTERNAL_IP

# Запрос к frontend (ответ приходит от backend)
curl -i http://$EXTERNAL_IP/
```

Ожидаемый ответ:

```
HTTP/1.1 200 OK
{"message": "Hello from backend!", "pod": "backend-xxxxxxxxxx-xxxxx", "path": "/"}
```

Проверка балансировки между репликами (в выводе должны быть разные поды):

```bash
for i in $(seq 1 15); do curl -s http://$EXTERNAL_IP/ | grep -o '"pod": "[^"]*"'; done | sort | uniq -c
```

Backend доступен изнутри кластера, но не снаружи:

```bash
kubectl run tmp --rm -it --image=busybox --restart=Never -- wget -qO- http://backend-service:5000/
kubectl get svc backend-service     # EXTERNAL-IP: <none>
```

### Проверка отказоустойчивости и масштабирования

```bash
# Удалить под backend — Deployment создаст новый
kubectl delete pod $(kubectl get pods -l app=backend -o name | head -1)
kubectl get pods -l app=backend

# Изменить число реплик
kubectl scale deployment backend --replicas=5
kubectl get pods -l app=backend
kubectl scale deployment backend --replicas=3
```

### Логи

```bash
kubectl logs -l app=backend --tail=10
kubectl logs -l app=frontend --tail=10
```

## Остановка и очистка

```bash
kubectl delete -f k8s/      # удалить приложение
minikube stop               # остановить кластер
minikube delete             # удалить кластер полностью
```

## Возможные проблемы

| Симптом | Причина и решение |
|---|---|
| `ErrImagePull` / `ImagePullBackOff` | Образ не собран внутри minikube. Повторить `minikube image build ...` для backend и frontend |
| `EXTERNAL-IP` — `<pending>` | Не запущен `minikube tunnel` |
| `curl: (3) URL rejected` | Переменная `EXTERNAL_IP` пуста, см. предыдущий пункт |
| `502 Bad Gateway` | Backend ещё не готов, проверить `kubectl get pods` |
| Поды в `CrashLoopBackOff` | Смотреть `kubectl logs <pod>` и `kubectl describe pod <pod>` |
