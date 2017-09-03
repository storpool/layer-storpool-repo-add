from __future__ import print_function

import time
import subprocess

from charms import reactive
from charmhelpers.core import hookenv

from spcharms import repo as sprepo
from spcharms import utils as sputils

def key_data():
	return 'pub:-:2048:1:7FF335CEB2E5AAA2:'

def repo_url():
	return hookenv.config().get('storpool_repo_url')
	
def rdebug(s):
	sputils.rdebug(s, prefix='repo-add')

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
	reactive.set_state('storpool-repo-add.update-apt')
	reactive.remove_state('storpool-repo-add.updated-apt')

def report_no_config():
	rdebug('no StorPool configuration yet')
	if hookenv.status_get() != 'active':
		hookenv.status_set('maintenance', 'waiting for the StorPool configuration')

@reactive.when('storpool-repo-add.install-apt-key')
@reactive.when_not('storpool-repo-add.configured')
def no_config_for_apt_key():
	report_no_config()

@reactive.when('storpool-repo-add.install-apt-repo')
@reactive.when_not('storpool-repo-add.configured')
def no_config_for_apt_repo():
	report_no_config()

@reactive.when('storpool-repo-add.update-apt')
@reactive.when_not('storpool-repo-add.configured')
def no_config_for_apt_update():
	report_no_config()

@reactive.when('storpool-repo-add.configured')
@reactive.when('storpool-repo-add.install-apt-key')
@reactive.when_not('storpool-repo-add.installed-apt-key')
def do_install_apt_key():
	rdebug('install-apt-key invoked')
	if hookenv.status_get() != 'active':
		hookenv.status_set('maintenance', 'checking for the APT key')

	if not has_apt_key():
		install_apt_key()

	rdebug('install-apt-key seems fine')
	if hookenv.status_get() != 'active':
		hookenv.status_set('maintenance', '')
	reactive.set_state('storpool-repo-add.installed-apt-key')

@reactive.when('storpool-repo-add.configured')
@reactive.when('storpool-repo-add.install-apt-repo')
@reactive.when_not('storpool-repo-add.installed-apt-repo')
def do_install_apt_repo():
	rdebug('install-apt-repo invoked')
	if hookenv.status_get() != 'active':
		hookenv.status_set('maintenance', 'checking for the APT repository')

	if not has_apt_repo():
		install_apt_repo()

	rdebug('install-apt-repo seems fine')
	if hookenv.status_get() != 'active':
		hookenv.status_set('maintenance', '')
	reactive.set_state('storpool-repo-add.installed-apt-repo')

@reactive.when('storpool-repo-add.configured')
@reactive.when('storpool-repo-add.update-apt')
@reactive.when('storpool-repo-add.installed-apt-repo')
@reactive.when_not('storpool-repo-add.updated-apt')
def do_update_apt():
	rdebug('invoking apt-get update')
	if hookenv.status_get() != 'active':
		hookenv.status_set('maintenance', 'updating the APT cache')

	subprocess.check_call(['apt-get', 'update'])

	rdebug('update-apt seems fine')
	if hookenv.status_get() != 'active':
		hookenv.status_set('maintenance', '')
	reactive.set_state('storpool-repo-add.updated-apt')

	# And, finally, the others can do stuff, too
	reactive.set_state('storpool-repo-add.available')

def trigger_check_and_install():
	reactive.set_state('storpool-repo-add.install-apt-key')
	reactive.set_state('storpool-repo-add.install-apt-repo')
	reactive.remove_state('storpool-repo-add.installed-apt-key')
	reactive.remove_state('storpool-repo-add.installed-apt-repo')

def trigger_check_install_and_update():
	trigger_check_and_install()
	reactive.set_state('storpool-repo-add.update-apt')
	reactive.remove_state('storpool-repo-add.updated-apt')

@reactive.hook('install')
def install():
	rdebug('storpool-repo-add.install invoked')
	trigger_check_install_and_update()

@reactive.hook('upgrade-charm')
def upgrade():
	rdebug('storpool-repo-add.upgrade-charm invoked')
	reactive.remove_state('storpool-repo-add.configured')
	trigger_check_install_and_update()

@reactive.hook('config-changed')
def try_config():
	rdebug('config-changed')
	config = hookenv.config()

	repo_url = config.get('storpool_repo_url', None)
	if repo_url is None:
		rdebug('no repository URL set in the config yet')
		reactive.remove_state('storpool-repo-add.configured')
	else:
		rdebug('got a repository URL: {url}'.format(url=repo_url))
		reactive.set_state('storpool-repo-add.configured')

@reactive.hook('update-status')
def check_status_and_well_okay_install():
	rdebug('storpool-repo-add.update-status invoked')
	reactive.set_state('storpool-repo-add.check-and-install')
	trigger_check_and_install()

@reactive.when('storpool-repo-add.stop')
@reactive.when_not('storpool-repo-add.stopped')
def stop():
	rdebug('storpool-repo-add stopping as requested')
	reactive.remove_state('storpool-repo-add.stop')
	reactive.remove_state('storpool-repo-add.install-apt-key')
	reactive.remove_state('storpool-repo-add.install-apt-repo')
	reactive.remove_state('storpool-repo-add.update-apt')
	reactive.remove_state('storpool-repo-add.configured')
	reactive.set_state('storpool-repo-add.stopped')
	hookenv.status_set('maintenance', '')
