# Kubernetes Deployment

This folder contains manifests to deploy **Asset Manager** and **PostgreSQL** on a Kubernetes cluster.

## 1) Create namespace (optional)
```bash
kubectl apply -f kubernetes/namespace.yaml
```

## 2) Apply secrets and config
Update the values in `kubernetes/secret.yaml` before applying.

```bash
kubectl apply -f kubernetes/secret.yaml
kubectl apply -f kubernetes/configmap.yaml
```

## 3) Create persistent volumes
```bash
kubectl apply -f kubernetes/web-pvc.yaml
```

## 4) Deploy PostgreSQL
```bash
kubectl apply -f kubernetes/postgres-statefulset.yaml
kubectl apply -f kubernetes/postgres-service.yaml
```

## 5) Deploy Asset Manager
```bash
kubectl apply -f kubernetes/web-deployment.yaml
kubectl apply -f kubernetes/web-service.yaml
```

## 6) Access the app

For local clusters:
```bash
kubectl port-forward svc/assetmanager-web 5000:80
```

Open:
```
http://localhost:5000
```

## 7) (Optional) Ingress
Use `kubernetes/ingress.yaml` if you have an ingress controller installed.

```bash
kubectl apply -f kubernetes/ingress.yaml
```

Update the hostname inside the ingress file to your domain.
