## Usage: tag.sh package_name bump_type prerelease [--latest <version>] [--dry-run]
##   --latest <version>  Use the specified version as the latest version
##   --dry-run           Do not create any tags, just print the version
##
## Example:
##   tag.sh ansible-maia.installation major alpha --latest v1.0.0
##   tag.sh ansible-maia.build-images patch beta --dry-run
##
## If --latest is specified, the next argument is used as the version.
## If --dry-run is specified, no tags are created, just the version is printed.
## BUMP_TYPE can be major, minor, patch
## PRERELEASE can be alpha, beta, rc, etc.

if [ "$1" == "--help" ]; then
  echo "Usage: tag.sh package_name bump_type prerelease [--latest <version>] [--dry-run]"
  echo "  --latest <version>  Use the specified version as the latest version"
  echo "  --dry-run           Do not create any tags, just print the version"
  echo "  package_name can be ansible-maia.installation or ansible-maia.build-images."
  echo "  bump_type can be major, minor, patch"
  echo "  prelease can be alpha, beta, rc, etc."
  exit 0
fi
# Get latest tag (descending, semver)
if [ "$1" == "ansible-maia.installation" ]; then
LATEST=v$(git tag -l 'ansible-maia.installation-v*' --sort=-v:refname | head -n 1 | sed 's/^ansible-maia.installation-v//')
elif [ "$1" == "ansible-maia.build-images" ]; then
LATEST=v$(git tag -l 'ansible-maia.build-images-v*' --sort=-v:refname | head -n 1 | sed 's/^ansible-maia.build-images-v//')
else
LATEST=$(git tag --sort=-v:refname | head -n 1)
fi
# Uncomment below (for debugging, override found tag)
#LATEST=v0.0.0

# Check for --latest override and use next argument as version
for i in "$@"; do
  if [ "$i" = "--latest" ]; then
    pos=$(( $(echo "$@" | tr ' ' '\n' | grep -n -- --latest | cut -d: -f1) + 1 ))
    LATEST=$(echo "$@" | cut -d' ' -f$pos)
    break
  fi
done


echo "Latest tag: $LATEST"

if [ -z "$LATEST" ] || [ "$LATEST" = "v" ]; then
  echo "No tags found"
  LATEST="v1.0.0"
  echo "Using default tag: $LATEST"
fi

VERSION=${LATEST#v}
# Regex for semver and prerelease: <MAJOR>.<MINOR>.<PATCH> or <MAJOR>.<MINOR>.<PATCH>-<PRERELEASE>.<N>
VERSION_RE="^([0-9]+)\.([0-9]+)\.([0-9]+)(-([a-zA-Z]+)\.([0-9]+))?$"

if [[ $VERSION =~ $VERSION_RE ]]; then
  MAJOR="${BASH_REMATCH[1]}"
  MINOR="${BASH_REMATCH[2]}"
  PATCH="${BASH_REMATCH[3]}"
  LATEST_PRERELEASE="${BASH_REMATCH[5]}"
  LATEST_PRERELEASE_N="${BASH_REMATCH[6]}"
else
  echo "Could not parse version: $VERSION"
  exit 1
fi

BUMP_TYPE="$2"
PRERELEASE="$3"
if [[ "$PRERELEASE" == --* ]]; then
  PRERELEASE=""
fi

# Default to current values
NEXT_MAJOR=$MAJOR
NEXT_MINOR=$MINOR
NEXT_PATCH=$PATCH
NEXT_PRERELEASE=""
NEXT_PRERELEASE_N=""

if [[ -z "$PRERELEASE" && -z "$LATEST_PRERELEASE" ]]; then
  if [[ "$BUMP_TYPE" == "major" ]]; then
    NEXT_MAJOR=$((MAJOR + 1))
    NEXT_MINOR=0
    NEXT_PATCH=0
  elif [[ "$BUMP_TYPE" == "minor" ]]; then
    NEXT_MINOR=$((MINOR + 1))
    NEXT_PATCH=0
  elif [[ "$BUMP_TYPE" == "patch" ]]; then
    NEXT_PATCH=$((PATCH + 1))
  fi
fi

if [[ -n "$PRERELEASE" ]]; then
  if [[ "$LATEST_PRERELEASE" == "$PRERELEASE" ]] && \
     [[ "$MAJOR" -eq "$NEXT_MAJOR" ]] && \
     [[ "$MINOR" -eq "$NEXT_MINOR" ]] && \
     [[ "$PATCH" -eq "$NEXT_PATCH" ]]; then
    # Same prerelease, just bump number
    if [[ -n "$LATEST_PRERELEASE_N" ]]; then
      NEXT_PRERELEASE_N=$((LATEST_PRERELEASE_N + 1))
    else
      NEXT_PRERELEASE_N=1
    fi
  else
    # New prerelease, start from 1
    NEXT_PRERELEASE_N=1
  fi
  NEXT_VER="v$NEXT_MAJOR.$NEXT_MINOR.$NEXT_PATCH-$PRERELEASE.$NEXT_PRERELEASE_N"
else
  # No prerelease requested
  if [[ -n "$LATEST_PRERELEASE" ]] && \
     [[ "$MAJOR" -eq "$NEXT_MAJOR" ]] && \
     [[ "$MINOR" -eq "$NEXT_MINOR" ]] && \
     [[ "$PATCH" -eq "$NEXT_PATCH" ]]; then
    # Was prerelease but no longer requested, keep as-is (do not bump anything)
    NEXT_VER="v$MAJOR.$MINOR.$PATCH"
  else
    NEXT_VER="v$NEXT_MAJOR.$NEXT_MINOR.$NEXT_PATCH"
  fi
fi


if [ "$1" == "ansible-maia.installation" ]; then
  NEXT_VER="ansible-maia.installation-$NEXT_VER"
elif [ "$1" == "ansible-maia.build-images" ]; then
  NEXT_VER="ansible-maia.build-images-$NEXT_VER"
fi
echo "Tagging $NEXT_VER"

if [[ "$*" == *"--dry-run"* ]]; then
  echo "Dry run: Not creating any tags."
  exit 0
fi

echo "Do you want to push the tag? (y/n)"
read push_tag
if [[ "$push_tag" == "y" ]]; then
  if [ "$1" == "ansible" ]; then
    git tag -s $NEXT_VER -m "Ansible MAIA.Installation $NEXT_VER"
  else
    git tag -s $NEXT_VER -m "$NEXT_VER"
  fi
  git push --tags
fi

# Delete the local tag if it already exists
#if git rev-parse "$NEXT_VER" >/dev/null 2>&1; then
#  echo "Deleting local tag $NEXT_VER"
  #git tag -d "$NEXT_VER"
#fi

# Delete the remote tag if it exists
#if git ls-remote --tags origin | grep -q "refs/tags/$NEXT_VER$"; then
#  echo "Deleting remote tag $NEXT_VER"
  #git push --delete origin "$NEXT_VER"
#fi
