"""
A Juju charm layer that adds the StorPool Ubuntu package repository to
the node's APT configuration.
"""

from __future__ import print_function

import os
import tempfile
import subprocess

from charms import reactive
from charmhelpers.core import hookenv

from spcharms import status as spstatus
from spcharms import utils as sputils


def key_data():
    """
    Hardcode the StorPool package signing key.
    """
    return 'pub:-:2048:1:7FF335CEB2E5AAA2:'


def repo_url():
    """
    Get the StorPool package repository URL from the configuration.
    """
    return hookenv.config().get('storpool_repo_url')


def rdebug(s):
    """
    Pass the diagnostic message string `s` to the central diagnostic logger.
    """
    sputils.rdebug(s, prefix='repo-add')


def has_apt_key():
    """
    Check whether the local APT installation has the StorPool signing key.
    """
    rdebug('has_apt_key() invoked')
    current = subprocess.check_output([
                                       'apt-key',
                                       'adv',
                                       '--list-keys',
                                       '--batch',
                                       '--with-colons'
                                      ])
    kdata = key_data()
    return bool(list(filter(
        lambda s: s.startswith(kdata),
        current.decode().split('\n')
    )))


def has_apt_repo():
    """
    Check whether the local APT installation has the StorPool repository.
    """
    rdebug('has_apt_repo() invoked')
    current = subprocess.check_output(['apt-cache', 'policy'])
    # OK, well, maybe this is better done with a regular expression...
    url = repo_url()
    return bool(list(filter(
        lambda s: s.find(url) != -1,
        current.decode().split('\n')
    )))


def install_apt_key():
    """
    Add the StorPool package signing key to the local APT setup.
    """
    rdebug('install_apt_key() invoked')
    keyfile = '{charm}/templates/{fname}'.format(charm=hookenv.charm_dir(),
                                                 fname='storpool-maas.key')
    rdebug('about to invoke apt-key add {keyfile}'.format(keyfile=keyfile))
    subprocess.check_call(['apt-key', 'add', keyfile])


def install_apt_repo():
    """
    Add the StorPool package repository to the local APT setup.
    """
    rdebug('install_apt_repo() invoked')

    rdebug('cleaning up the /etc/apt/sources.list file first')
    sname = '/etc/apt/sources.list'
    with open(sname, mode='r') as f:
        with tempfile.NamedTemporaryFile(dir='/etc/apt',
                                         mode='w+t',
                                         delete=False) as tempf:
            removed = 0
            for line in f.readlines():
                if 'https://debian.ringlet.net/storpool-maas' in line or \
                   'https://debian.ringlet.net/storpool-juju' in line or \
                   'http://repo.storpool.com/storpool-maas' in line or \
                   '@repo.storpool.com/storpool-maas' in line:
                    removed = removed + 1
                    continue
                print(line, file=tempf, end='')

            if removed:
                rdebug('Removing {removed} lines from {sname}'
                       .format(removed=removed, sname=sname))
                tempf.flush()
                os.rename(tempf.name, sname)
            else:
                rdebug('No need to remove any lines from {sname}'
                       .format(sname=sname))
                os.unlink(tempf.name)

    rdebug('invoking add-apt-repository')
    subprocess.check_call(['add-apt-repository', '-y', repo_url()])
    reactive.set_state('storpool-repo-add.update-apt')
    reactive.remove_state('storpool-repo-add.updated-apt')


def report_no_config():
    """
    Note that the `storpool_repo_url` has not been set yet.
    """
    rdebug('no StorPool configuration yet')
    spstatus.npset('maintenance', 'waiting for the StorPool configuration')


@reactive.when('storpool-repo-add.install-apt-key')
@reactive.when_not('storpool-repo-add.configured')
def no_config_for_apt_key():
    """
    Note that the `storpool_repo_url` has not been set yet.
    """
    report_no_config()


@reactive.when('storpool-repo-add.install-apt-repo')
@reactive.when_not('storpool-repo-add.configured')
def no_config_for_apt_repo():
    """
    Note that the `storpool_repo_url` has not been set yet.
    """
    report_no_config()


@reactive.when('storpool-repo-add.update-apt')
@reactive.when_not('storpool-repo-add.configured')
def no_config_for_apt_update():
    """
    Note that the `storpool_repo_url` has not been set yet.
    """
    report_no_config()


@reactive.when('storpool-repo-add.configured')
@reactive.when('storpool-repo-add.install-apt-key')
@reactive.when_not('storpool-repo-add.installed-apt-key')
def do_install_apt_key():
    """
    Check and, if necessary, install the StorPool package signing key.
    """
    rdebug('install-apt-key invoked')
    spstatus.npset('maintenance', 'checking for the APT key')

    if not has_apt_key():
        install_apt_key()

    rdebug('install-apt-key seems fine')
    spstatus.npset('maintenance', '')
    reactive.set_state('storpool-repo-add.installed-apt-key')


@reactive.when('storpool-repo-add.configured')
@reactive.when('storpool-repo-add.install-apt-repo')
@reactive.when_not('storpool-repo-add.installed-apt-repo')
def do_install_apt_repo():
    """
    Check and, if necessary, add the StorPool repository.
    """
    rdebug('install-apt-repo invoked')
    spstatus.npset('maintenance', 'checking for the APT repository')

    if not has_apt_repo():
        install_apt_repo()

    rdebug('install-apt-repo seems fine')
    spstatus.npset('maintenance', '')
    reactive.set_state('storpool-repo-add.installed-apt-repo')


@reactive.when('storpool-repo-add.configured')
@reactive.when('storpool-repo-add.update-apt')
@reactive.when('storpool-repo-add.installed-apt-repo')
@reactive.when_not('storpool-repo-add.updated-apt')
def do_update_apt():
    """
    Invoke `apt-get update` to fetch data from the StorPool repository.
    """
    rdebug('invoking apt-get update')
    spstatus.npset('maintenance', 'updating the APT cache')

    subprocess.check_call(['apt-get', 'update'])

    rdebug('update-apt seems fine')
    spstatus.npset('maintenance', '')
    reactive.set_state('storpool-repo-add.updated-apt')

    # And, finally, the others can do stuff, too
    reactive.set_state('storpool-repo-add.available')


def trigger_check_and_install():
    """
    Force a check and installation of the key and the repository.
    """
    spstatus.reset_unless_error()
    reactive.set_state('storpool-repo-add.install-apt-key')
    reactive.set_state('storpool-repo-add.install-apt-repo')
    reactive.remove_state('storpool-repo-add.installed-apt-key')
    reactive.remove_state('storpool-repo-add.installed-apt-repo')


def trigger_check_install_and_update():
    """
    Force a full check-install-update cycle.
    """
    trigger_check_and_install()
    reactive.set_state('storpool-repo-add.update-apt')
    reactive.remove_state('storpool-repo-add.updated-apt')


@reactive.hook('install')
def install():
    """
    Run a full check-install-update cycle upon first installation.
    """
    rdebug('storpool-repo-add.install invoked')
    trigger_check_install_and_update()


@reactive.hook('upgrade-charm')
def upgrade():
    """
    Run a full check-install-update cycle upon charm upgrade.
    """
    rdebug('storpool-repo-add.upgrade-charm invoked')
    reactive.remove_state('storpool-repo-add.configured')
    trigger_check_install_and_update()


@reactive.hook('config-changed')
def try_config():
    """
    Check if the configuration has been fully set.
    """
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
    """
    Periodically check for the key and the repository, but do not
    necessarily force an update.
    """
    rdebug('storpool-repo-add.update-status invoked')
    reactive.set_state('storpool-repo-add.check-and-install')
    trigger_check_and_install()


@reactive.when('storpool-repo-add.stop')
@reactive.when_not('storpool-repo-add.stopped')
def stop():
    """
    Clean up and no longer attempt to install anything.
    """
    rdebug('storpool-repo-add stopping as requested')
    reactive.remove_state('storpool-repo-add.stop')
    reactive.remove_state('storpool-repo-add.install-apt-key')
    reactive.remove_state('storpool-repo-add.install-apt-repo')
    reactive.remove_state('storpool-repo-add.update-apt')
    reactive.remove_state('storpool-repo-add.configured')
    reactive.set_state('storpool-repo-add.stopped')
    spstatus.npset('maintenance', '')
