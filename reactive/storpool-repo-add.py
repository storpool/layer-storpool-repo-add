from __future__ import print_function

import pwd
import os
import time
import subprocess

#from charmhelpers.core.hookenv import status_set
#from charmhelpers.core.templating import render

from charms import reactive
from charmhelpers.core import hookenv

def key_data():
	return 'pub:-:2048:1:7FF335CEB2E5AAA2:'

def repo_url():
	return 'https://debian.ringlet.net/storpool-maas'
	
def rdebug(s):
	with open('/tmp/storpool-charms.log', 'a') as f:
		print('{tm} [repo-add] {s}'.format(tm=time.ctime(), s=s), file=f)

def has_apt_key():
	rdebug('has_apt_key() invoked')
	current = subprocess.check_output(['apt-key', 'adv', '--list-keys', '--batch', '--with-colons'])
	kdata = key_data()
	return bool(list(filter(
		lambda s: s.startswith(kdata),
		current.decode().split('\n')
	)))

def has_apt_repo():
	rdebug('has_apt_repo() invoked')
	current = subprocess.check_output(['apt-cache', 'policy'])
	# OK, well, maybe this is better done with a regular expression...
	url = repo_url()
	return bool(list(filter(
		lambda s: s.find(url) != -1,
		current.decode().split('\n')
	)))

def install_apt_key():
	rdebug('install_apt_key() invoked')
	keyfile = '{charm}/templates/{fname}'.format(charm=hookenv.charm_dir(), fname='storpool-maas.key')
	rdebug('about to invoke apt-key add {keyfile}'.format(keyfile=keyfile))
	subprocess.check_call(['apt-key', 'add', keyfile])

def install_apt_repo():
	rdebug('install_apt_repo() invoked')
	rdebug('invoking add-apt-repository')
	subprocess.check_call(['add-apt-repository', '-y', repo_url()])
	rdebug('invoking apt-get update')
	subprocess.check_call(['apt-get', 'update'])

def check_and_install():
	hookenv.status_set('maintenance', 'checking for the APT key')
	if not has_apt_key():
		install_apt_key()

	hookenv.status_set('maintenance', 'checking for the APT repository')
	if not has_apt_repo():
		install_apt_repo()

	hookenv.status_set('active', '')
	if not reactive.is_state('storpool-repo-add.available'):
		reactive.set_state('storpool-repo-add.available')

@reactive.hook('install')
def install():
	rdebug('storpool-repo-add.install invoked')
	check_and_install()

@reactive.hook('upgrade-charm')
def upgrade():
	rdebug('storpool-repo-add.upgrade-charm invoked')
	check_and_install()

@reactive.hook('update-status')
def check_status_and_well_okay_install():
	rdebug('storpool-repo-add.update-status invoked')
	check_and_install()

@reactive.when('repo.available', 'storpool-repo-add.available')
def notify_repo_setup(remote):
	rdebug('whee, letting a remote unit know that our repo is available')
	remote.configure(True)

### @when('apache.available', 'database.available')
### def setup_vanilla(mysql):
###     render(source='vanilla_config.php',
###            target='/var/www/vanilla/conf/config.php',
###            owner='www-data',
###            perms=0o775,
###            context={
###                'db': mysql,
###            })
###     uid = pwd.getpwnam('www-data').pw_uid
###     os.chown('/var/www/vanilla/cache', uid, -1)
###     os.chown('/var/www/vanilla/uploads', uid, -1)
###     set_state('apache.start')
###     status_set('maintenance', 'Starting Apache')
### 
### 
### @when('apache.available')
### @when_not('database.connected')
### def missing_mysql():
###     remove_state('apache.start')
###     status_set('blocked', 'Please add relation to MySQL')
### 
### 
### @when('database.connected')
### @when_not('database.available')
### def waiting_mysql(mysql):
###     remove_state('apache.start')
###     status_set('waiting', 'Waiting for MySQL')
### 
### 
### @when('apache.started')
### def started():
###     status_set('active', 'Ready')
