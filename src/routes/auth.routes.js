// src/routes/auth.routes.js
const express = require('express');
const router = express.Router();
const passport = require('passport');
const authController = require('../controllers/auth.controller');
const authMiddleware = require('../middleware/auth.middleware');

router.post('/register', authController.register);
router.post('/login', authController.login);

// Google OAuth routes
router.get('/google',
  passport.authenticate('google', { scope: ['profile', 'email'] })
);

router.get('/google/callback',
  passport.authenticate('google', { failureRedirect: '/login' }),
  (req, res) => {
    const token = jwt.sign(
      { id: req.user.id, email: req.user.email },
      process.env.JWT_SECRET,
      { expiresIn: '24h' }
    );
    res.redirect(`${process.env.CLIENT_URL}?token=${token}`);
  }
);

// Protected route example
router.get('/profile', authMiddleware, (req, res) => {
    res.json({ user: req.user });
  });
  
  module.exports = router;