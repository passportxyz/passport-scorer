# Internal Embed API

## API endpoints to test

### Validate API keys

`curl -X GET  http://core-alb.private.gitcoin.co/embed/validate-api-key -H 'X-API-KEY: <API KEY HERE>' -I`

### Post stamps

```bash
curl -X POST  http://core-alb.private.gitcoin.co/embed/stamps/0x85fF01cfF157199527528788ec4eA6336615C989 \
-H 'X-API-KEY: <API KEY HERE>' \
-d '{"scorer_id":"6","stamps":[]}'
```
