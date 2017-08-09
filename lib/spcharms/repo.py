import os
import re
import subprocess

from charmhelpers.core import hookenv

class StorPoolRepoException(Exception):
	pass

re_policy = {
	'installed': re.compile('\s* Installed: \s+ (?P<version> \S+ ) \s* $', re.X),
	'candidate': re.compile('\s* Candidate: \s+ (?P<version> \S+ ) \s* $', re.X),
}

def apt_pkg_policy(names):
	res = {}
	for pkg in names:
		pres = {}
		bad = False
		pb = subprocess.check_output(['apt-cache', 'policy', '--', pkg])
		for line in pb.decode().split('\n'):
			for pol in re_policy:
				m = re_policy[pol].match(line)
				if not m:
					continue
				if pol in pres:
					bad = True
					break
				pres[pol] = m.groupdict()['version']
			if bad:
				break

		for pol in re_policy:
			if pol not in pres:
				bad = True
				break
			elif pres[pol] == '(none)':
				pres[pol] = None

		if bad:
			res[pkg] = None
		else:
			res[pkg] = pres

	return res

def pkgs_to_install(requested, policy):
	to_install = []

	for p in policy:
		ver = policy[p]
		if ver is None:
			return ('could not obtain APT policy information about the {pkg} package'.format(pkg=p), None)

		req = requested[p]
		if ver['installed'] is not None and (req == '*' or req == ver['installed']):
			continue
		elif ver['candidate'] is None:
			return ('the {pkg} package is not available in the repositories, cannot proceed'.format(pkg=p), None)
		elif req != '*' and req != ver['candidate']:
			return ('the {req} version of the {pkg} package is not available in the repositories, we have {cand} instead'.format(req=req, pkg=p, cand=ver['candidate']), None)

		to_install.append(p)

	return (None, to_install)

def apt_install(pkgs):
	previous_b = subprocess.check_output([
		'dpkg-query', '-W', '--showformat',
		'${Package}\t${Version}\t${Status}\n'
	])
	previous = dict(map(
		lambda d: (d[0], d[1]),
		filter(
			lambda d: len(d) == 3 and d[2].startswith('install'),
			map(
				lambda s: s.split('\t'),
				previous_b.decode().split('\n')
			)
		)
	))

	cmd = ['apt-get', 'install', '-y', '--no-install-recommends', '--']
	cmd.extend(pkgs)
	subprocess.check_call(cmd)

	current_b = subprocess.check_output([
		'dpkg-query', '-W', '--showformat',
		'${Package}\t${Version}\t${Status}\n'
	])
	current = dict(map(
		lambda d: (d[0], d[1]),
		filter(
			lambda d: len(d) == 3 and d[2].startswith('install'),
			map(
				lambda s: s.split('\t'),
				current_b.decode().split('\n')
			)
		)
	))

	newly_installed = list(filter(
		lambda name: name not in previous or previous[name] != current[name],
		current.keys()
	))
	return newly_installed

def install_packages(requested):
	try:
		policy = apt_pkg_policy(requested.keys())
	except Exception as e:
		return ('Could not query the APT policy for "{names}": {err}'.format(names=sorted(list(requested.keys())), err=e), None)

	(err, to_install) = pkgs_to_install(requested, policy)
	if err is not None:
		return (err, None)

	try:
		return (None, apt_install(to_install))
	except Exception as e:
		return ('Could not install the "{names}" packages: {e}'.format(names=sorted(to_install), e=e), None)

def pkg_record_file():
	return '/var/lib/' + hookenv.charm_name() + '.packages'

def charm_install_flag_dir():
	return '/var/lib/storpool/install-charms'

def charm_install_flag_file():
	return charm_install_flag_dir() + '/' + hookenv.charm_name()

def charm_install_list_file():
	return '/var/lib/storpool/install-charms.txt'

def record_packages(names):
	if not os.path.isdir('/var/lib/storpool'):
		os.mkdir('/var/lib/storpool', mode=0o700)
	if not os.path.isdir('/var/lib/storpool/install-charms'):
		os.mkdir('/var/lib/storpool/install-charms', mode=0o700)
	with open(charm_install_flag_file(), mode='w') as flagf:
		pass
	with open(charm_install_list_file(), mode='a') as listf:
		print('\n'.join(names), file=listf)

def uninstall_recorded_packages():
	try:
		os.unlink(charm_install_flag_file())
	except Exception as e:
		pass
	
	if not os.path.isdir(charm_install_flag_dir()) or \
	   not list(filter(
		lambda e: e.is_file(),
		os.scandir(charm_install_flag_dir())
	   )):
		if os.path.isfile(charm_install_list_file()):
			with open(charm_install_list_file(), 'r') as listf:
				names = sorted(set(list(filter(
					lambda s: len(s) > 0,
					map(
						lambda d: d.rstrip(),
						listf.readlines()
					)
				))))
				if names:
					cmd = ['apt-get', 'remove', '-y', '--']
					cmd.extend(names)
					subprocess.call(cmd)

			os.remove(charm_install_list_file())

def list_package_files(name):
	files_b = subprocess.check_output(['dpkg', '-L', '--', name])
	return sorted(filter(
		lambda s: len(s) > 0,
		files_b.decode().split('\n')
	))
