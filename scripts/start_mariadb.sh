#!/bin/sh
# Local preview only: start MariaDB and ensure the CRM database/user exist.
mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld
DATADIR=/root/mariadb-data
if [ ! -d "$DATADIR/mysql" ]; then
  mkdir -p "$DATADIR"
  if [ -d /var/lib/mysql/mysql ]; then cp -a /var/lib/mysql/. "$DATADIR/"; else mysql_install_db --user=mysql --datadir="$DATADIR" >/dev/null; fi
fi
chown -R mysql:mysql "$DATADIR" && chmod 755 /root
(
  for i in $(seq 1 30); do mysqladmin -uroot ping >/dev/null 2>&1 && break; sleep 1; done
  mysql -uroot -e "CREATE DATABASE IF NOT EXISTS crm_maiharta CHARACTER SET utf8mb4;
    CREATE USER IF NOT EXISTS 'crm'@'127.0.0.1' IDENTIFIED BY 'crmpass';
    CREATE USER IF NOT EXISTS 'crm'@'localhost' IDENTIFIED BY 'crmpass';
    GRANT ALL ON crm_maiharta.* TO 'crm'@'127.0.0.1'; GRANT ALL ON crm_maiharta.* TO 'crm'@'localhost'; FLUSH PRIVILEGES;"
) &
exec /usr/bin/mysqld_safe --user=mysql --datadir="$DATADIR"
