// GitHub Pages — 100 % statique, pas de serveur
window.DRC_CONFIG = {
  apiBase: '',
  staticMode: true,
  basePath: '/drc',
  appUrl: 'https://klyontipe.github.io/drc/',
  // EmailJS (gratuit) : https://www.emailjs.com/
  // 1. Crée un compte → Service Gmail (davidramenecrepe@gmail.com)
  // 2. Template avec variables : {{to_email}} {{subject}} {{message}} {{app_url}}
  // 3. Remplis les 3 clés ci-dessous
  emailjs: {
    publicKey: 'bKOXPpGauh01KAKJg',
    serviceId: 'service_l2kg5vr',
    templateId: '', // Email Templates → ton template → Template ID
  },
};
