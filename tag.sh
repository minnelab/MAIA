# Get latest tag (descending, semver)
if [ "$1" == "ansible" ]; then
LATEST=v$(git tag -l 'ansible-maia.installation-v*' --sort=-v:refname | head -n 1 | sed 's/^ansible-maia.installation-v//')
else
LATEST=$(git tag --sort=-v:refname | head -n 1)
fi
# Uncomment below (for debugging, override found tag)
#LATEST=v0.0.0

echo "Latest tag: $LATEST"

VERSION=${LATEST#v}
# Allow versions with/without prerelease: <MAJOR>.<MINOR>.<PATCH> or <MAJOR>.<MINOR>.<PATCH>-<tag>.<n>
VERSION_RE="^([0-9]+)\.([0-9]+)\.([0-9]+)(-([a-zA-Z]+)\.([0-9]+))?$"
if [[ "$VERSION" =~ $VERSION_RE ]]; then
  MAJOR="${BASH_REMATCH[1]}"
  MINOR="${BASH_REMATCH[2]}"
  PATCH="${BASH_REMATCH[3]}"
  PRERELEASE_FULL="${BASH_REMATCH[4]}"      # (e.g. -alpha.1 or empty)
  PRERELEASE_TAG="${BASH_REMATCH[5]}"      # (e.g. alpha or empty)
  PRERELEASE_NUM="${BASH_REMATCH[6]}"      # (e.g. 1 or empty)
else
  echo "Version format not recognized: $VERSION"
  exit 1
fi

BUMP_TYPE="$2"
PRERELEASE_TYPE="$3"

NEXT_MAJOR=$MAJOR
NEXT_MINOR=$MINOR
NEXT_PATCH=$PATCH
NEXT_PRERELEASE_TAG=""
NEXT_PRERELEASE_NUM=""

if [[ -n "$PRERELEASE_TYPE" ]]; then
  # If prerelease type is provided, do not bump version numbers, unless this is the very first prerelease for this version (alpha.1, etc)
  # If current tag is not the same version and not already a prerelease, we allow the increment as usual (first alpha.1)
  if [[ -z "$PRERELEASE_TAG" ]]; then
    # Not a prerelease tag yet; do a normal version bump for first pre-release
    case "$BUMP_TYPE" in
      patch)
        NEXT_PATCH=$((PATCH+1))
        NEXT_MINOR=$MINOR
        NEXT_MAJOR=$MAJOR
        ;;
      minor)
        NEXT_PATCH=0
        NEXT_MINOR=$((MINOR+1))
        NEXT_MAJOR=$MAJOR
        ;;
      major)
        NEXT_PATCH=0
        NEXT_MINOR=0
        NEXT_MAJOR=$((MAJOR+1))
        ;;
      *)
        echo "Invalid bump type; use: patch, minor, major."
        exit 1
        ;;
    esac
  else
    # Already a prerelease, don't bump base version -- alpha.2/beta.1/etc:
    NEXT_PATCH=$PATCH
    NEXT_MINOR=$MINOR
    NEXT_MAJOR=$MAJOR
  fi
else
  # No prerelease type
  if [[ -n "$PRERELEASE_TAG" ]]; then
    # Latest is a pre-release, no new pre-release requested: keep base version!
    NEXT_MAJOR=$MAJOR
    NEXT_MINOR=$MINOR
    NEXT_PATCH=$PATCH
  else
    # No prerelease present; normal version bump
    case "$BUMP_TYPE" in
      patch)
        NEXT_PATCH=$((PATCH+1))
        NEXT_MINOR=$MINOR
        NEXT_MAJOR=$MAJOR
        ;;
      minor)
        NEXT_PATCH=0
        NEXT_MINOR=$((MINOR+1))
        NEXT_MAJOR=$MAJOR
        ;;
      major)
        NEXT_PATCH=0
        NEXT_MINOR=0
        NEXT_MAJOR=$((MAJOR+1))
        ;;
      *)
        echo "Invalid bump type; use: patch, minor, major."
        exit 1
        ;;
    esac
  fi
fi

if [[ -n "$PRERELEASE_TYPE" ]]; then
  # Want alpha/beta/rc bump
  if [[ "$PRERELEASE_TAG" == "$PRERELEASE_TYPE" ]]; then
    # Already a pre-release of this type; increment
    NEXT_PRERELEASE_NUM=$((PRERELEASE_NUM + 1))
  else
    # Not a pre-release of this type (or not a pre-release): start from 1
    NEXT_PRERELEASE_NUM=1
  fi
  NEXT_PRERELEASE_TAG=$PRERELEASE_TYPE
  NEXT_VER="v$NEXT_MAJOR.$NEXT_MINOR.$NEXT_PATCH-$NEXT_PRERELEASE_TAG.$NEXT_PRERELEASE_NUM"
else
  # No pre-release
  NEXT_VER="v$NEXT_MAJOR.$NEXT_MINOR.$NEXT_PATCH"
fi

if [ "$1" == "ansible" ]; then
  NEXT_VER="ansible-maia.installation-$NEXT_VER"
fi
echo "Tagging $NEXT_VER"

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