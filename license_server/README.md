# Métraplan — Serveur de Licences

## Démarrage rapide

```bash
cd license_server
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8765
```

Dashboard admin : http://localhost:8765/

## Variables d'environnement

| Variable       | Description                          | Défaut                          |
|----------------|--------------------------------------|---------------------------------|
| ADMIN_API_KEY  | Clé secrète pour les routes /admin   | metraplan-admin-secret-2026     |
| JWT_SECRET     | Secret de signature des tokens JWT   | metraplan-jwt-secret-2026       |

**⚠ Changez ces valeurs en production !**

## Routes API

### Routes admin (Header `x-admin-key` obligatoire)

| Méthode | Route               | Description                        |
|---------|---------------------|------------------------------------|
| POST    | /generate_license   | Générer une nouvelle clé           |
| GET     | /licenses           | Lister toutes les licences         |
| POST    | /block_license      | Bloquer / débloquer une licence    |

### Routes client

| Méthode | Route     | Description                        |
|---------|-----------|------------------------------------|
| POST    | /activate | Activer une clé (1ère fois)        |
| POST    | /verify   | Vérifier/renouveler le token JWT   |
| GET     | /health   | Santé du serveur                   |

## Exemple de clé générée

```
MTR-4R7X-K2QP-9WNB-3LMF
```

## Format du token JWT retourné au client

```json
{
  "license_key": "MTR-4R7X-K2QP-9WNB-3LMF",
  "machine_id":  "a3f9b2c1d4e5...",
  "expires_at":  "2027-06-08T00:00:00+00:00",
  "type":        "pro",
  "iat":         "2026-06-08T...",
  "exp":         "2026-06-15T..."
}
```
