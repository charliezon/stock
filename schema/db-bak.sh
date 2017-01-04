#!/bin/bash

# add "01 3 * * * root /root/stock/schema/db-bak.sh" into /etc/crontab first 
# run "sudo chmod 777 /root/stock/schema/db-bak.sh"
# run "sudo service cron restart"

#settings
DBHost=mysql
DBName=stock
DBUser=root
# TODO change password
DBPasswd=123456

BackupPath=/root/stock/db-bak/

LogFile=/root/stock/db-bak/db.log

BackupMethod=mysqldump

NewFile="$BackupPath"db$(date +%y%m%d).tgz
DumpFileName=db$(date +%y%m%d).sql
DumpFile="$BackupPath$DumpFileName"
OldFile="$BackupPath"db$(date +%y%m%d --date='5 days ago').tgz

echo "------------------------------------" >> $LogFile

echo $(date +"%y-%m-%d %H:%M:%S") >> $LogFile

echo "------------------------------------" >> $LogFile

#Delete old file

if [ -f $OldFile ]
then
  rm -f $OldFile >> $LogFile 2>&1
  echo "[$OldFile] Delete old file success!" >> $LogFile
else
  echo "[$OldFile] No old backup file." >> $LogFile
fi

if [ -f $NewFile ]
then
  echo "[$NewFile] The backup file exists. Can't backup!" >> $LogFile
else
  case $BackupMethod in
  mysqldump)
    if [ -z $DBPasswd ]
    then
      mysqldump -h $DBHost -u $DBUser --opt $DBName > $DumpFile
    else
      mysqldump -h $DBHost -u $DBUser -p$DBPasswd --opt $DBName > $DumpFile
    fi
    cd $BackupPath
    tar zcvPf $NewFile $DumpFileName >> $LogFile 2>&1
    echo "[$NewFile] Backup Success!" >> $LogFile
    rm -rf $DumpFile
    ;;
  esac
fi
echo "------------------------------------" >> $LogFile
  