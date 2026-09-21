# Exemples interopérables

- `worker_echo.py` : protocole worker JSON stdin/stdout, sans SDK dans le worker.
- `client.py` : client Python d'un service partagé ; URL en argument, token en environnement.
- `DotNetClient/` : client C# .NET 8 sans dépendance CyToolsCore Python.

Pour C# :

```powershell
dotnet build Examples/DotNetClient
$env:CYTOOLS_TOKEN = '<jeton-client>'
dotnet run --no-build --project Examples/DotNetClient -- http://127.0.0.1:8766/v1
```

Créer d'abord le client et démarrer `cytool-test serve` comme dans Docs/MultiClient.md.
Le client C# crée une session, soumet echo, attend et vérifie le résultat, puis ferme
la session. Ce programme illustre le protocole ; il n'est pas un SDK C# complet.
Un client C++ peut reproduire exactement ces requêtes avec sa bibliothèque HTTP/JSON.
