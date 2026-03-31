USE medicore;

UPDATE users
SET password_hash = '$argon2id$v=19$m=65536,t=3,p=4$+wXEdNi14BTubb3sS2TNAg$bsfvw6ORl9dMSep/D+I6FxQ1/PkhGvdc16RFDYpKf/g'
WHERE username = 'admin@medicore.local';
