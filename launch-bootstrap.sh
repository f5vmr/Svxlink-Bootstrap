#!/bin/sh

set -eu

BOOTSTRAP_REPOSITORY_URL='https:'\
'//github.com/f5vmr/Svxlink-Bootstrap.git'
BOOTSTRAP_BRANCH='main'
BOOTSTRAP_TEMPORARY_DIRECTORY=''

cleanup_bootstrap_checkout()
{
    case "${BOOTSTRAP_TEMPORARY_DIRECTORY}" in
        /tmp/svxlink-bootstrap.*)
            rm -rf -- "${BOOTSTRAP_TEMPORARY_DIRECTORY}"
            ;;
    esac
}

trap cleanup_bootstrap_checkout EXIT HUP INT TERM

if [ "$(id -u)" -ne 0 ]; then
    echo "SvxLink Bootstrap must be started with root authority." >&2
    echo "Run this launcher using sudo." >&2
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This launcher requires Debian or Raspberry Pi OS." >&2
    exit 1
fi

echo "Preparing SvxLink Bootstrap prerequisites..."

export DEBIAN_FRONTEND=noninteractive

apt-get update

apt-get install \
    --yes \
    --no-install-recommends \
    ca-certificates \
    git \
    python3 \
    python3-flask

BOOTSTRAP_TEMPORARY_DIRECTORY="$(
    mktemp -d /tmp/svxlink-bootstrap.XXXXXX
)"

echo "Obtaining SvxLink Bootstrap..."

git clone \
    --depth 1 \
    --branch "${BOOTSTRAP_BRANCH}" \
    --single-branch \
    "${BOOTSTRAP_REPOSITORY_URL}" \
    "${BOOTSTRAP_TEMPORARY_DIRECTORY}/repository"

cd "${BOOTSTRAP_TEMPORARY_DIRECTORY}/repository"

python3 web_manager.py
