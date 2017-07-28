#!/usr/bin/make -f

NAME?=		storpool-repo-add
SERIES?=	xenial

SRCS=		\
		layer.yaml \
		metadata.yaml \
		\
		reactive/storpool-repo-add.py \


TARGETDIR=	${CURDIR}/${SERIES}/${NAME}
BUILD_MANIFEST=	${TARGETDIR}/.build.manifest

all:	charm

charm:	${BUILD_MANIFEST}

${BUILD_MANIFEST}:	${SRCS}
	charm build -s '${SERIES}' -n '${NAME}'

clean:
	rm -rf -- '${TARGETDIR}'

deploy:	all
	juju deploy -- '${TARGETDIR}'

upgrade:	all
	juju upgrade-charm --path '${TARGETDIR}' -- '${NAME}'

.PHONY:	all charm clean deploy upgrade
