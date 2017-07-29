import re
import subprocess

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
