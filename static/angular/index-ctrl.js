app.factory('variable', function() {
    return {
        baseurl: "http://localhost:7000/api/",
        orgurl: "http://localhost:7000/api/",
    };
  })
  
  app.controller(
    "index-ctrl",
    function ($scope, $http, $window, $location,$interval,$timeout, variable) {
     
      $scope.init = function (req, res) {
       
         console.log("This is the init function")

         $scope.data = {}
         $scope.data.stock = "HDFCBANK"
         $scope.data.sourceexch =  "NSE"
         $scope.data.interval =  "3"
         $scope.data.length =  "500"
         $scope.data.qty =  "1"
         $scope.data.googlesheetname = "MA Backtesting"
         $scope.data.googlesheetnumber = "0"
         $scope.getprofitloss()
         $scope.getanalysisdata()

        
      };



      $scope.submitsettings = function (data) {
        console.log(data);
  
        var urlconfig = {
          headers: {
            "Content-Type": "application/json;",
          },
        };
  
        $http
          .post(variable.baseurl + "botsettings", data, urlconfig)
          .success(function (response, status, headers, config) {
            
              // $scope.profitloss = response.data
              console.log($scope.profitloss);
              $scope.getprofitloss();
  
          })
          .error(function (data, status, header, config) {
            console.log(data);
            $("#getportfolio-issue").modal("show");
          });
      };


      $scope.getprofitloss = function () {
        
  
        var urlconfig = {
          headers: {
            "Content-Type": "application/json;",
          },
        };
        
        data = {}
        $http
          .post(variable.baseurl + "getprofitloss", data, urlconfig)
          .success(function (response, status, headers, config) {
          
            $scope.chart(response) 
  
          })
          .error(function (data) {
            console.log("error")
            console.log(data);

            
          });
      };


      // This is the plotly graph for ease of understanding from console to final web presence

      
      $scope.chart = function (response) {

        xarray = []
        profitloss = []

        var data = JSON.parse(response.data);
        console.log(data);
      
        var i = 0;
        var winrate = 0
        
        for (i; i < data.length; i += 1) {

            xarray.push(i);
            profitloss.push(data[i]["profit_loss"]);
           
          if (data[i]["profit_loss"] > 0 ){
              winrate = winrate + 1 ;
            }

         }
        
        console.log(winrate)
        var loserate = data.length - winrate


        var trace1 = {
          x: xarray,
          y: profitloss,
          type: 'bar',
          name: 'Primary Product',
          marker: {
            color: '#4e8dc9',
            opacity: 0.8,
          }
        };
        
        
        var data = [trace1];
        
        var layout = {
          title: 'Profitloss Report',
          xaxis: {
            tickangle: -45
          },
          barmode: 'group',
          showlegend: false,
        };

        
        Plotly.newPlot('profitlossdiv', data, layout);


        
        
        //  Lets draw the pie-chart

        var data = [{
          values: [winrate, loserate],
          labels: ['Winrate', 'Loserate' ],
          marker: {'colors': [
            'rgb(0, 204, 0)',  
            'rgb(215, 11, 11)' 
           ]},
          domain: {column: 0},
          name: 'Winrate',
          hoverinfo: 'label+percent+name',
          hole: .4,
          type: 'pie'
        }];
        
        var layout = {
          title: 'Winrate',
          annotations: [
            {
              font: {
                size: 18
              },
              showarrow: false,
              text: '',
              x: 0.17,
              y: 0.5
            }
          ],
          height: 300,
          width: 300,
          showlegend: false,
          grid: {rows: 1, colums: 1}
        };
        
        Plotly.newPlot('winratediv', data, layout);
        


        
      };

      
      $scope.getanalysisdata = function () {
        
  
        var urlconfig = {
          headers: {
            "Content-Type": "application/json;",
          },
        };
        
        data = {
            'stock' : "HDFCBANK"
        }

        $http
          .post(variable.baseurl + "graphdata", data, urlconfig)
          .success(function (response, status, headers, config) {
            
           
            $scope.analysisgraph(response) 
  
          })
          .error(function (data) {
            console.log("error")
            console.log(data);
          });
      };

      $scope.analysisgraph = function (response) {
        
        dataindex = []
        datadatetime = []
        dataclose = []
        datama = []
        dataema = []
        
        i = 0;
       
        var data = response.data
        console.log(data)



        for (i; i < data.length; i += 1) {

      
            console.log(data[i]["datetime"])
            // var dtdate = new moment(response.data[i]['datetime']).format("YYYY-MM-DD HH:MM");
            dataindex.push(response.data[i]["index"])
            dataclose.push(response.data[i]["close"]);
            datama.push(response.data[i]["ma"]);
            dataema.push(response.data[i]["ema"]);
        
          }
       
   
        var fig = {}
  
          fig.data = [
        {
          x: dataindex,
          y: dataclose,
          smoothness :1.3,
          line_smoothing:1.3,
          mode: 'line+marker',
          marker: {color: "blue",size: 1 },
          name: 'close'
        },

        {
          x: dataindex,
          y: datama,
          smoothness :1.3,
          line_smoothing:1.3,
          mode: 'line+marker',
          marker: {color: "orange",size: 1 },
          name: 'close'
        },
        
       
     
        
      ];
  
      console.log(fig.data);
      fig.layout = {}
      fig.layout.title = 'Portfolio Tracking';
      Plotly.newPlot('analysisgraph', fig.data, fig.layout)
  
      }




     
    }
  );