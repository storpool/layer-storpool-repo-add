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

from spcharms import config as spconfig
from spcharms import states as spstates
from spcharms import status as spstatus
from spcharms import utils as sputils

APT_CONFIG_DIR = '/etc/apt'
APT_SOURCES_DIR = 'sources.list.d'
APT_SOURCES_FILE = 'storpool-maas.list'
APT_KEYRING_DIR = 'trusted.gpg.d'
APT_KEYRING_FILE = 'storpool-maas.gpg'


def apt_sources_list():
    """
    Generate the name of the APT file to store the StorPool repo data.
    """
    return '{dir}/{subdir}/{file}'.format(dir=APT_CONFIG_DIR,
                                          subdir=APT_SOURCES_DIR,
                                          file=APT_SOURCES_FILE)


def apt_keyring():
    """
    Generate the name of the APT file to store the StorPool OpenPGP key.
    """
    return '{dir}/{subdir}/{file}'.format(dir=APT_CONFIG_DIR,
                                          subdir=APT_KEYRING_DIR,
                                          file=APT_KEYRING_FILE)


def key_data():
    """
    Hardcode the StorPool package signing key.
    """
    return 'pub:-:2048:1:7FF335CEB2E5AAA2:'


def repo_url():
    """
    Get the StorPool package repository URL from the configuration.
    """
    return spconfig.m()['storpool_repo_url']


def rdebug(s):
    """
    Pass the diagnostic message string `s` to the central diagnostic logger.
    """
    sputils.rdebug(s, prefix='repo-add')


def apt_file_contents(url):
    """
    Generate the text that should be put into the APT sources list.
    """
    return {
        'mandatory': 'deb {url} xenial main'.format(url=url),
        'optional': 'deb-src {url} xenial main'.format(url=url),
    }


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
    filename = apt_sources_list()
    if not os.path.isfile(filename):
        return False

    contents = apt_file_contents(repo_url())
    with open(filename, mode='r') as f:
        found_mandatory = False
        for line in map(lambda s: s.strip(), f.readlines()):
            if line == contents['mandatory']:
                found_mandatory = True
            elif contents['optional'] not in line:
                return False
        return found_mandatory


def install_apt_key():
    """
    Add the StorPool package signing key to the local APT setup.
    """
    rdebug('install_apt_key() invoked')
    keyfile = '{charm}/templates/{fname}'.format(charm=hookenv.charm_dir(),
                                                 fname='storpool-maas.key')
    filename = apt_keyring()
    dirname = os.path.dirname(filename)
    if not os.path.isdir(dirname):
        rdebug('- creating the {dir} directory first'.format(dir=dirname))
        os.mkdir(dirname, 0o755)
    rdebug('about to invoke apt-key add {keyfile}'.format(keyfile=keyfile))
    subprocess.check_call(['apt-key', '--keyring', filename, 'add', keyfile])


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

    contents = apt_file_contents(repo_url())
    text = '{mandatory}\n# {optional}\n'.format(**contents)
    filename = apt_sources_list()
    rdebug('creating the {fname} file'.format(fname=filename))
    rdebug('contents: {text}'.format(text=text))
    dirname = os.path.dirname(filename)
    if not os.path.isdir(dirname):
        rdebug('- creating the {dir} directory first'.format(dir=dirname))
        os.mkdir(dirname, mode=0o755)
    with tempfile.NamedTemporaryFile(dir=dirname,
                                     mode='w+t',
                                     prefix='.storpool-maas.',
                                     suffix='.list',
                                     delete=False) as tempf:
        print(text, file=tempf, end='', flush=True)
        os.rename(tempf.name, filename)

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


STATES_REDO = {
    'set': [
        'storpool-repo-add.install-apt-key',
        'storpool-repo-add.install-apt-repo',
        'storpool-repo-add.update-apt',
        'storpool-repo-add.configure',
    ],
    'unset': [
        'storpool-repo-add.installed-apt-key',
        'storpool-repo-add.installed-apt-repo',
        'storpool-repo-add.updated-apt',
        'storpool-repo-add.configured',
    ],
}


@reactive.hook('install')
def install():
    """
    Run a full check-install-update cycle upon first installation.
    """
    rdebug('storpool-repo-add.install invoked')
    spstates.register('storpool-repo-add', {
        'config-changed': STATES_REDO,
        'upgrade-charm': STATES_REDO,
    })
    spstates.handle_single(STATES_REDO)


@reactive.when('storpool-helper.config-set')
@reactive.when('storpool-repo-add.configure')
@reactive.when_not('storpool-repo-add.configured')
def try_config():
    """
    Check if the configuration has been fully set.
    """
    rdebug('reconfigure')
    reactive.remove_state('storpool-repo-add.configure')
    spstatus.reset_if_allowed('storpool-repo-add')
    config = spconfig.m()

    repo_url = config.get('storpool_repo_url', None)
    if repo_url is None or repo_url == '':
        rdebug('no repository URL set in the config yet')
        reactive.remove_state('storpool-repo-add.configured')
    else:
        rdebug('got a repository URL: {url}'.format(url=repo_url))
        reactive.set_state('storpool-repo-add.configured')


@reactive.when('storpool-repo-add.stop')
@reactive.when_not('storpool-repo-add.stopped')
def stop():
    """
    Clean up and no longer attempt to install anything.
    """
    rdebug('storpool-repo-add stopping as requested')

    for fname in (apt_sources_list(), apt_keyring()):
        if os.path.isfile(fname):
            rdebug('- trying to remove {name}'.format(name=fname))
            try:
                os.unlink(fname)
            except Exception as e:
                rdebug('  - could not remove {name}: {e}'
                       .format(name=fname, e=e))
        else:
            rdebug('- no {name} to remove'.format(name=fname))

    for state in STATES_REDO['set'] + STATES_REDO['unset']:
        reactive.remove_state(state)

    reactive.remove_state('storpool-repo-add.stop')
    reactive.set_state('storpool-repo-add.stopped')
    spstatus.npset('maintenance', '')
