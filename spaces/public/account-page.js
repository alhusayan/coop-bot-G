import {accountReturnPath} from './account-navigation.js';
let path='/';try{path=accountReturnPath(sessionStorage.getItem('spaces-account-return-path'));}catch{}
location.replace(path+location.search+location.hash);
