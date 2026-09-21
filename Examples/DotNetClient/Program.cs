using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text;

// No dependency on the Python SDK: only the CyTools JSON wire contract.
if (args.Length != 1) throw new ArgumentException("Usage: DotNetClient URL");
var endpoint = new Uri(args[0]);
if (endpoint.Scheme != "https" && !(endpoint.Scheme == "http" && endpoint.IsLoopback))
    throw new ArgumentException("Remote endpoints require HTTPS");
using var handler = new HttpClientHandler { AllowAutoRedirect = false };
using var http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(30) };
http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue(
    "Bearer", Environment.GetEnvironmentVariable("CYTOOLS_TOKEN")
              ?? throw new InvalidOperationException("Set CYTOOLS_TOKEN"));
int requestId = 0;
async Task<JsonElement> Call(string method, object parameters)
{
    // The portable v1 HTTP endpoint uses Content-Length (no chunked request bodies).
    using var body = new StringContent(JsonSerializer.Serialize(
        new { protocolVersion = "1.0", id = ++requestId, method, @params = parameters }),
        Encoding.UTF8, "application/json");
    using var response = await http.PostAsync(endpoint, body);
    response.EnsureSuccessStatusCode();
    using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
    if (document.RootElement.TryGetProperty("error", out var error))
        throw new InvalidOperationException(error.ToString());
    return document.RootElement.GetProperty("result").Clone();
}
var session = await Call("CreateSession", new { });
var sessionId = session.GetProperty("sessionId").GetString();
var job = await Call("SubmitJob", new {
    sessionId, operationId = "echo", parameters = new { text = "Hello from C#" },
    executionTimeout = 10, queueTimeout = 10
});
var jobId = job.GetProperty("jobId").GetString();
var deadline = DateTime.UtcNow.AddSeconds(30);
while (job.GetProperty("state").GetString() is not ("Completed" or "Failed" or "Cancelled"))
{
    if (DateTime.UtcNow > deadline) throw new TimeoutException("Job still active; inspect before retrying");
    await Task.Delay(30);
    job = await Call("GetJob", new { jobId });
}
Console.WriteLine(job.GetRawText());
await Call("CloseSession", new { sessionId });
return job.GetProperty("state").GetString() == "Completed" ? 0 : 1;
