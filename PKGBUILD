# Maintainer: Jorge <jorgeescalera500@gmail.com>
pkgname=spotman
pkgver=1.0.0
pkgrel=1
pkgdesc="TUI manager de Spotify (Textual): edita, mueve, crea, limpia, fusiona, ordena e importa playlists desde la terminal"
arch=('any')
url="https://github.com/jorgeTTPD/spotman"
license=('MIT')
depends=('python' 'python-rich' 'python-textual' 'python-requests' 'python-dotenv')
makedepends=('python-build' 'python-installer' 'python-wheel' 'python-setuptools')
source=("${pkgname}-${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
  cd "${srcdir}/spotman-${pkgver}"
  python -m build --wheel --no-isolation
}

package() {
  cd "${srcdir}/spotman-${pkgver}"
  python -m installer --destdir="${pkgdir}" dist/*.whl
}
