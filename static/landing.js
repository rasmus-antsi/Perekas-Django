const navToggle = document.querySelector('.landing-nav-toggle')
const navLinks = document.querySelector('.landing-nav-links')
const navActions = document.querySelector('.landing-nav-actions')

if (navToggle) {
  navToggle.addEventListener('click', () => {
    navToggle.classList.toggle('open')
    navLinks.classList.toggle('open')
    navActions.classList.toggle('open')
  })
}
