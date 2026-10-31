.PHONY: ci install dev test lint build docker

# Run by .github/workflows/_ci.yml
ci: install lint test build

install:
	npm ci

dev:
	npm run dev

test:
	npm test

lint:
	npm run lint

build:
	npm run build

docker:
	docker build -t shopops-web .
