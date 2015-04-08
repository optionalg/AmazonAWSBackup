#!/usr/local/bin/python
# -*- coding: utf-8 -*-

# Written for Python 2.7

# *******************************************
# Backup Script for Amazon AWS
# *******************************************

'''There are some things that Bash is awesome at and there are some things
that Python is awesome at -- the original bash script is actually much better
suited for this job. As such, this is sort of a bastardized (mostly Python) 
implementation of COMPANYbackup.sh. One of the things that Python excels at is 
readability, so I'm sacrificing succinctness for clarity.

Because I lack the same environment, most of this code is completely 
untested. While not a great way to code, it's at least usable for showing an 
example piece.'''


import os
import fnmatch
import time
import datetime
import socket
import platform
import subprocess

# for the email capability
import smtplib
from email.mime.text import MIMEText

log_file_location = "/backups/logs/"
current_date = time.strftime("%Y-%m-%d")
date_time = time.strftime("%Y-%m-%d %H:%M:%S")
email_for_alert = "sysnotify@COMPANY.com"
hostname = socket.gethostname()
matches = []

# old_account_names is not used in current version of bash file, so not
# included here
logs_account_names = [log_file_location, "account_names"]
days_log = [log_file_location, current_date, '.log']

# so that we start fresh, which apparently the bash file wants
account_names = open( "".join(logs_account_names), 'w')
log = open( "".join(days_log), 'w')


def send_email(receiver, text):
    # create a basic text email and send
    # because if we're gonna so this, we're gonna do it right
    message = open(text, 'rb')
    email = MIMEText( message.read() )
    message.close()

    email['Subject'] = "Backup - {}".format(hostname)
    email['From'] = "{} at AWS".format(hostname)
    email['To'] = email_for_alert

    try:
        smtp_email = smtplib.SMTP('localhost')
        smtp_email.sendmail(hostname, email_for_alert, email)
        smtp_email.quit()
    except SMTPException: # catch everything for now
        print("{ERROR - unable to send email!")


def run_command(command):
    '''Runs commands with the ability to read the output as opposed to just
    knowing if it succeeded or not.'''
    p = subprocess.Popen(command,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    return iter(p.stdout.readline, b'')


def wordpress_optimize():
    '''runs the command stored and returns an error if something goes wrong.'''
    result = subprocess.check_call(
        '/usr/bin/php-cli /usr/local/bin/wp db optimize --allow-root', 
        shell = True)
    return result


def wordpress_export(account, c_date = current_date):
    result = subprocess.check_call(
        '/usr/bin/php-cli /usr/local/bin/wp db export {} {}".sql" --allow-root'.format(acc, c_date),
        shell = True)
    return result


def create_backup(account, c_date = current_date):
    result = subprocess.check_call(
        'tar -vczf /backups/{}{}".tar.gz" * .htaccess .COMPANY.com.data'.format(account, c_date),
        shell = True)
    os.remove('{}{}.sql'.format(account, c_date))
    return result


def send_backup_to_aws(account, c_date = current_date, hostname = hostname):
    result = subprocess.check_call(
        's3cmd --config=/root/.s3cfg put -r /backups/{}{}".tar.gz" s3://COMPANYwpbackups/{}/{}/'.format(
            account, c_date, hostname, account),
        shell = True)
    return result


def delete_aws_file(filename):
    result = subprocess.check_call(
        's3cmd del {}'.format(filename),
        shell = True)
    return result


# Need to check /srv if ubuntu distribution, /home if centos
os_version = platform.dist()
home_directory = "/home/" # ubuntu by default

'''Need to be usable without changing script on either centos or ubuntu. We
check for redhat because centos 5 or below reports as redhat, so we might as
well catch that too.'''
if os_version[0].lower() is 'redhat' or os_version[0].lower() is 'centos':
    home_directory = "/srv/"

for root, dirnames, files in os.walk(home_directory):
    for filename in fnmatch.filter(files, '.COMPANY.com.data'):
        matches.append(os.path.join(root, filename))

'''Take the .COMPANY.com.data file and read it. Each one has two lines - the first
is the account name, the second is the absolute path to their directory.'''

for loc in matches:
    
    COMPANY_file = open(loc, r)
    lines = COMPANY_file.readlines()
    account_n = lines[0]
    path_to_install = lines[1]
    COMPANY_file.close()

    account_names.write(account_n)
    log.write("{} - INFO: starting process for {}".format(date_time, account_n))

    os.chdir(path_to_install)

    log.write("{} - INFO: starting wp db optimize for {}".format(date_time, account_n))
    if wordpress_optimize() is 0:
        log.write("{} - INFO: starting wp db export sql for {}".format(date_time, account_n))
        
        if wordpress_export(account_n) is 0:
            log.write("{} - INFO: starting creation of backup file for {}".format(date_time, account_n))
        
            if create_backup(account_n) is 0:
                log.write("{} - INFO: putting backup file to COMPANYwpbackups for {}".format(date_time, account_n))
        
                if send_backup_to_aws(account_n) is 0:
                    log.write("{} - INFO: backup file successfully uploaded for {}".format(date_time, account_n))
        
                else:
                    log.write("{} - ERROR: failed uplodating of backup file for {}".format(date_time, account_n))
        
            else:
                log.write("{} - ERROR: failed to create backup for {}".format(date_time, account_n))
        
        else:
            log.write("{} - ERROR: failed wp db export for {}".format(date_time, account_n))
    
    else:
        log.write("{} - ERROR: failed wp db optimize for {}".format(date_time, account_n))

    # *******************************************
    # Delete S3 backups older than 30 days
    # *******************************************

    log.write("")
    log.write("{} - INFO: deleting starting (files more than 30 days)".format(date_time))

    for line in run_command('s3cmd --config=/root/.s3cfg ls s3://COMPANYwpbackups/{}/{}/'.format(hostname, account_n)):
        try:
            file_date = datetime.datetime.strptime(line[0:9], "%Y-%m-%d")
        except ValueError:
            # the line we're on does not contain a date here. Ignore and move on.
            pass

        if file_date < (current_date - datetime.timedelta(days = -30) ):
            # the + 1 is to account for the / between the account and the filename
            file_name_index_start = (line.find(account_n) + len(account_n) + 1)
            file_name = line[file_name_index_start:len(line)]
            log.write("{} - INFO: deleting {}".format(date_time, file_name))

            if delete_aws_file(file_name) is not 0:
                log.write("{} - ERROR: file deletion failed - {}".format(date_time, file_name))

account_names.close()
log.close()

send_email(email_for_alert, days_log)
