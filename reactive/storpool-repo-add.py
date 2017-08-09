from __future__ import print_function

import time
import subprocess

from charms import reactive
from charmhelpers.core import hookenv

from spcharms import repo as sprepo

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

	hookenv.status_set('maintenance', '')

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

@reactive.when('storpool-repo-add.stop')
@reactive.when_not('storpool-repo-add.stopped')
def stop():
	rdebug('storpool-repo-add stopping as requested')
	reactive.remove_state('storpool-repo-add.stop')
	hookenv.status_set('maintenance', 'checking if any OS packages need to be removed')
	try:
		sprepo.uninstall_recorded_packages()
		reactive.set_state('storpool-repo-add.stopped')
		hookenv.status_set('maintenance', '')
	except Exception as e:
		rdebug('could not uninstall the recorded packages: {e}'.format(e=e))
		hookenv.status_set('maintenance', 'failed to check for and/or remove OS packages')
