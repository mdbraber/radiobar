.PHONY: clean build

default: clean build install

clean:
	rm -rf dist/ build/

build:	clean
	python setup.py py2app

install: build
	rm -rf /Applications/RadioBar.app/
	cp -a dist/RadioBar.app /Applications/
