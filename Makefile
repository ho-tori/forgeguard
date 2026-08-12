.PHONY: test demo verify

test:
	python -m unittest discover -s tests -v

demo:
	python -m forgeguard demo

verify: test demo

