# Téléchargements

`DownloadManager(root, timeout=30)` gère des fichiers HTTPS indépendamment du fournisseur.
Hugging Face, GitHub Releases et dépôts officiels personnalisés peuvent fournir leurs
URLs et headers ; les politiques de comptes, dépôts privés et licences appartiennent
à l'adaptateur de la source. Le Core ne contourne aucun accès gated.

```python
manager.download('weights.bin', url, sha256=expected_sha256, size=expected_size,
                 headers={'Authorization': 'Bearer ' + token},
                 license_accepted=accepted,
                 pause=pause_event, cancellation=cancellation_token,
                 progress=lambda downloaded, total: None,
                 revision=repository_revision)
```

Le fichier partiel `.part` et ses métadonnées `.download.json` sont persistés.
La reprise utilise Range et If-Range/ETag quand possible. Un serveur qui renvoie 200
au lieu de 206 entraîne un redémarrage propre du fichier ; une plage incohérente ou
un ETag changé dans une réponse partielle est refusé. Sans ETag ni SHA256 attendu,
le téléchargement repart de zéro pour éviter de mélanger des versions.

Pause retourne l'état Paused ; rappeler download avec les mêmes informations reprend,
y compris après redémarrage de l'application. Une annulation interrompt la lecture,
conserve le partiel pour reprise ; remove supprime les fichiers du nom concerné.
Le timeout borne une attente réseau, pas une durée globale arbitraire de gros download.
L'intégrité SHA256 et la taille attendue sont vérifiées avant le remplacement atomique
du fichier final. verify permet une vérification ultérieure ; list_installed retourne
les fichiers finalisés. Repair : vérifier puis relancer download avec le hash attendu.
Update : fournir la nouvelle URL/révision et son nouveau hash, ou un nom versionné.

Les credentials sont uniquement en mémoire. Les redirections cross-host retirent
Authorization/Cookie. Les URLs de téléchargement sont persistées : fournir une URL
stable sans secret en query string. Un fichier hash-invalide est supprimé, jamais
présenté comme installé. Les retries réseau sont explicites : le caller rappelle
download, ce qui reprend le partiel conservé.

Le mode HTTP en clair est refusé, sauf allow_test_http sur loopback pour les tests.
Un manager sérialise ses appels ; ne pas utiliser plusieurs managers concurrents
sur la même destination. Le contrôle d'intégrité fourni par la source est fortement
préférable à la seule taille ; ETag seul n'est pas une signature cryptographique.
