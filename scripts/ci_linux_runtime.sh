#!/usr/bin/env bash
# Install CI dependencies from signed Ubuntu archives without runner mirrorlists.
set -euo pipefail
if [[ "${GITHUB_ACTIONS:-}" != true ]]; then
    echo 'This installer is restricted to disposable GitHub Actions runners.' >&2
    exit 2
fi
source /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_CODENAME" != jammy ]]; then
    echo 'Review the supported build platform before changing Ubuntu releases.' >&2
    exit 2
fi
task_apt_dir=$(mktemp -d /tmp/ocready-apt.XXXXXX)
trap 'sudo rm -rf -- "$task_apt_dir"' EXIT
mkdir "$task_apt_dir/lists"
chmod 755 "$task_apt_dir" "$task_apt_dir/lists"
task_archive=https://archive.ubuntu.com/ubuntu
task_security=https://security.ubuntu.com/ubuntu
task_selected=false
# The alternative is also used in Canonical's Landscape mirror examples.
# Every InRelease and package still requires Ubuntu's archive signatures.
for task_transport in official princeton; do
    if [[ "$task_transport" == princeton ]]; then
        task_archive=https://mirror.math.princeton.edu/pub/ubuntu
        task_security=$task_archive
    fi
    task_reachable=true
    for task_suite in jammy jammy-updates jammy-security; do
        task_host=$task_archive
        [[ "$task_suite" != jammy-security ]] || task_host=$task_security
        if ! curl --fail --silent --show-error --location --connect-timeout 5 --max-time 15 \
            --max-filesize 1000000 --output /dev/null "$task_host/dists/$task_suite/InRelease"; then
            task_reachable=false
            break
        fi
    done
    if [[ "$task_reachable" == true ]]; then
        task_selected=true
        break
    fi
done
if [[ "$task_selected" != true ]]; then
    echo 'No configured signed Ubuntu transport is reachable; dependency setup failed.' >&2
    exit 1
fi
echo "Ubuntu package transport: $task_archive; security: $task_security"
cat > "$task_apt_dir/sources.list" <<SOURCES
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $task_archive jammy main restricted universe multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $task_archive jammy-updates main restricted universe multiverse
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] $task_security jammy-security main restricted universe multiverse
SOURCES
task_apt_options=(
    -o "Dir::Etc::sourcelist=$task_apt_dir/sources.list"
    -o 'Dir::Etc::sourceparts=-'
    -o "Dir::State::lists=$task_apt_dir/lists"
    -o 'APT::Update::Error-Mode=any'
    -o 'Acquire::Retries=2'
    -o 'Acquire::http::Timeout=30'
    -o 'Acquire::https::Timeout=30'
)
sudo apt-get "${task_apt_options[@]}" update
sudo apt-get "${task_apt_options[@]}" install --no-install-recommends -y "$@"
