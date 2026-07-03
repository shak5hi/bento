
const fs = require('fs');
const svg = fs.readFileSync('./src/assets/lightlogo.svg', 'utf8');
const match = svg.match(/data:image\/png;base64,([^"']+)/);
if (match && match[1]) {
  fs.writeFileSync('./src/assets/lightlogo.png', Buffer.from(match[1], 'base64'));
  console.log('Successfully saved lightlogo.png');
} else {
  console.log('No base64 png found');
}

