var app = angular.module('website', ['angular-storage', 'angularPayments','chart.js']);
app.config(['storeProvider', function(storeProvider) {
    storeProvider.setStore('sessionStorage');

}]);




