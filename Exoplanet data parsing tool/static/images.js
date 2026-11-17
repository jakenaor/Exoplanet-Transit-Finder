//MARK: image tab thingies
const ImageThing = Id => document.getElementById(Id);
const StarCanvas = ImageThing('StarCanvas');
const StarPen = StarCanvas.getContext('2d');
let ImageRun = null;
let StarThingies = [];
let PreviewThing = null;
let PreviewPixels = null;
let ImageBusy = false;
let UploadStopThing = null;
let ImagePollTimer = null;
let ImageGeneration = 0;
const ImageSaveKey = 'transit-image-work-v1';

if (window.parent !== window)
  document.body.classList.add('EmbeddedImages');

//MARK: status and buttons
function ImageStatus(Text)
{
  ImageThing('ImageStatus').textContent = Text;
}

function RefreshImageButtons()
{
  const Running = ImageBusy || ['running', 'cancelling'].includes(ImageRun?.status);
  ImageThing('PrepareImages').disabled = Running;
  ImageThing('ScienceImages').disabled = Running;
  ImageThing('DarkImages').disabled = Running;
  ImageThing('ProcessImages').disabled = Running || !PreviewThing || !StarThingies.length || !ImageRun?.science_count || !ImageRun?.dark_count;
  ImageThing('ProcessImages').textContent = ImageRun?.status === 'completed' ? 'Measure again' : 'Make time–flux table';
  ImageThing('CancelImages').disabled = !UploadStopThing && !['running', 'cancelling'].includes(ImageRun?.status);
  ImageThing('ImageToFinder').disabled = Running || ImageRun?.status !== 'completed' || !(ImageRun?.result?.usable_frames >= 2);
  ImageThing('UndoStar').disabled = Running || !StarThingies.length;
  for (const Id of ['StarRole', 'ApertureRadius', 'SkyInner', 'SkyOuter', 'TrackRadius', 'ImageClock', 'ImageWorkers'])
    ImageThing(Id).disabled = Running;
}

async function ImageApi(Path, Options = {})
{
  const Reply = await fetch(Path, Options);
  const Data = await Reply.json();
  if (!Reply.ok)
  {
    const ErrorThing = new Error(Data.error || 'Image request failed.');
    ErrorThing.status = Reply.status;
    throw ErrorThing;
  }
  return Data;
}

function PostImageJson(Path, Data, Extra = {})
{
  return ImageApi(Path, {...Extra, method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(Data)});
}

//MARK: keep the star picks if the page gets refreshed
function ImageOptions()
{
  return {stars:StarThingies, radius:Number(ImageThing('ApertureRadius').value), inner:Number(ImageThing('SkyInner').value),
    outer:Number(ImageThing('SkyOuter').value), tracking:Number(ImageThing('TrackRadius').value),
    timestamp:ImageThing('ImageClock').value, workers:Number(ImageThing('ImageWorkers').value)};
}

function SaveImageSetup()
{
  try
  {
    localStorage.setItem(ImageSaveKey, JSON.stringify({id:ImageRun?.id, options:ImageOptions()}));
  }
  catch (ErrorThing)
  {
    // private browsing can block storage. the running job still works.
  }
}

//MARK: image pixels and aperture circles
async function LoadImagePreview(Generation = ImageGeneration)
{
  const RunId = ImageRun?.id;
  const Preview = await ImageApi('/image-runs/' + RunId + '/preview');
  if (Generation !== ImageGeneration || ImageRun?.id !== RunId)
    return;
  const Pixels = new Image();
  await new Promise((Resolve, Reject) =>
  {
    Pixels.onload = Resolve;
    Pixels.onerror = () => Reject(new Error('Could not display the FITS preview.'));
    Pixels.src = 'data:image/png;base64,' + Preview.png;
  });
  if (Generation !== ImageGeneration || ImageRun?.id !== RunId)
    return;
  PreviewThing = Preview;
  PreviewPixels = Pixels;
  StarCanvas.width = Preview.width;
  StarCanvas.height = Preview.height;
  ImageThing('PreviewHeading').textContent = Preview.name;
  ImageThing('PreviewNote').textContent = Preview.image_width + ' × ' + Preview.image_height + ' original pixels. ' + Preview.note;
  DrawStarThingies();
}

function DrawStarThingies()
{
  StarPen.fillStyle = '#111827';
  StarPen.fillRect(0, 0, StarCanvas.width, StarCanvas.height);
  if (PreviewPixels)
    StarPen.drawImage(PreviewPixels, 0, 0);
  const Factor = PreviewThing?.factor || 1;
  const Radii = [Number(ImageThing('ApertureRadius').value), Number(ImageThing('SkyInner').value), Number(ImageThing('SkyOuter').value)];
  StarThingies.forEach((Star, Index) =>
  {
    StarPen.strokeStyle = Index === 0 ? '#fbbf24' : '#34d399';
    StarPen.fillStyle = StarPen.strokeStyle;
    StarPen.lineWidth = 1.5;
    Radii.forEach((Radius, R) =>
    {
      if (!Number.isFinite(Radius) || Radius <= 0)
        return;
      StarPen.setLineDash(R ? [3, 3] : []);
      StarPen.beginPath();
      StarPen.arc((Star[0] + .5) / Factor, (Star[1] + .5) / Factor, Radius / Factor, 0, Math.PI * 2);
      StarPen.stroke();
    });
    StarPen.setLineDash([]);
    StarPen.font = 'bold 15px system-ui';
    StarPen.fillText(Index ? 'C' + Index : 'T', (Star[0] + .5) / Factor + 8, (Star[1] + .5) / Factor - 8);
  });
  ImageThing('StarList').replaceChildren();
  const Labels = StarThingies.length ? StarThingies.map((Star, Index) => (Index ? 'Comparison ' + Index : 'Target') + ' · x ' + Star[0].toFixed(1) + ', y ' + Star[1].toFixed(1)) : ['No stars selected.'];
  for (const Text of Labels)
  {
    const Item = document.createElement('li');
    Item.textContent = Text;
    ImageThing('StarList').append(Item);
  }
  RefreshImageButtons();
}

StarCanvas.addEventListener('click', EventThing =>
{
  if (!PreviewThing || ImageBusy || ['running', 'cancelling'].includes(ImageRun?.status))
    return;
  const Box = StarCanvas.getBoundingClientRect();
  const X = (EventThing.clientX - Box.left) / Box.width * StarCanvas.width * PreviewThing.factor - .5;
  const Y = (EventThing.clientY - Box.top) / Box.height * StarCanvas.height * PreviewThing.factor - .5;
  const Star = [Math.max(0, Math.min(PreviewThing.image_width - 1, X)), Math.max(0, Math.min(PreviewThing.image_height - 1, Y))];
  if (ImageThing('StarRole').value === 'target')
  {
    StarThingies[0] = Star;
    ImageThing('StarRole').value = 'comparison';
  }
  else if (!StarThingies.length)
    return ImageStatus('Pick the target star first.');
  else if (StarThingies.length < 9)
    StarThingies.push(Star);
  else
    return ImageStatus('Up to eight comparison stars can be selected.');
  DrawStarThingies();
  SaveImageSetup();
});

ImageThing('UndoStar').addEventListener('click', () =>
{
  StarThingies.pop();
  if (!StarThingies.length)
    ImageThing('StarRole').value = 'target';
  DrawStarThingies();
  SaveImageSetup();
});

for (const Id of ['ApertureRadius', 'SkyInner', 'SkyOuter', 'TrackRadius', 'ImageClock', 'ImageWorkers'])
  ImageThing(Id).addEventListener('change', () => { DrawStarThingies(); SaveImageSetup(); });

//MARK: upload files one by one so ram does not go brr
ImageThing('PrepareImages').addEventListener('click', async () =>
{
  if (ImageBusy || ['running', 'cancelling'].includes(ImageRun?.status))
    return;
  const Science = Array.from(ImageThing('ScienceImages').files || []);
  const Darks = Array.from(ImageThing('DarkImages').files || []);
  if (!Science.length || !Darks.length)
    return ImageStatus('Choose science images and dark frames first.');
  const Files = [...Science.map(File => ({File, Kind:'science'})), ...Darks.map(File => ({File, Kind:'dark'}))];
  if (Science.length > 10000 || Darks.length > 128 || Files.some(({File}) => File.size > 512 * 1024 ** 2) || Files.reduce((Total, {File}) => Total + File.size, 0) > 20 * 1024 ** 3)
    return ImageStatus('Choose up to 10,000 science images and 128 darks, at most 512 MiB each and 20 GiB total.');
  if (Files.some(({File}) => !/\.(fits|fit|fts)$/i.test(File.name)))
    return ImageStatus('Choose individual FITS images; ZIP archives are not supported.');
  const Generation = ++ImageGeneration;
  window.clearTimeout(ImagePollTimer);
  const Controller = new AbortController();
  UploadStopThing = Controller;
  ImageBusy = true;
  ImageRun = null;
  StarThingies = [];
  PreviewThing = null;
  PreviewPixels = null;
  ImageThing('ImageResults').hidden = true;
  RefreshImageButtons();
  try
  {
    const Created = await PostImageJson('/image-runs', {}, {signal:Controller.signal});
    if (Generation !== ImageGeneration)
      return;
    ImageRun = Created;
    SaveImageSetup();
    const RunId = ImageRun.id;
    const Progress = ImageThing('ImageProgress');
    Progress.hidden = false;
    Progress.max = Files.length;
    Progress.value = 0;
    // shitty idea for these huge camera files:
    // await Promise.all(Files.map(File => File.arrayBuffer()));
    // one file at a time pls.
    for (let Index = 0; Index < Files.length; Index++)
    {
      const {File, Kind} = Files[Index];
      ImageStatus('Uploading ' + (Index + 1) + '/' + Files.length + ': ' + File.name + ' (' + (File.size / 1048576).toFixed(1) + ' MiB)');
      const Form = new FormData();
      Form.append('image', File);
      const Uploaded = await ImageApi('/image-runs/' + RunId + '/frames?kind=' + Kind, {method:'POST', body:Form, signal:Controller.signal});
      if (Generation !== ImageGeneration || ImageRun?.id !== RunId)
        return;
      ImageRun = Uploaded;
      Progress.value = Index + 1;
    }
    await LoadImagePreview(Generation);
    if (Generation !== ImageGeneration)
      return;
    ImageStatus(ImageRun.science_count + ' science images and ' + ImageRun.dark_count + ' darks loaded. Click the target star, then optional comparison stars.');
    ImageThing('StarRole').value = 'target';
  }
  catch (ErrorThing)
  {
    if (Generation === ImageGeneration)
      ImageStatus(ErrorThing.name === 'AbortError' ? 'Upload cancelled.' : ErrorThing.message);
  }
  finally
  {
    if (Generation === ImageGeneration)
    {
      ImageBusy = false;
      UploadStopThing = null;
      RefreshImageButtons();
    }
  }
});

//MARK: process, poll, and cancel
ImageThing('ProcessImages').addEventListener('click', async () =>
{
  if (!ImageRun || ImageBusy || ['running', 'cancelling'].includes(ImageRun.status))
    return;
  const RunId = ImageRun.id;
  const Options = ImageOptions();
  const Generation = ++ImageGeneration;
  window.clearTimeout(ImagePollTimer);
  ImageBusy = true;
  RefreshImageButtons();
  try
  {
    const Started = await PostImageJson('/image-runs/' + RunId + '/process', Options);
    if (Generation !== ImageGeneration || ImageRun?.id !== RunId)
      return;
    ImageRun = Started;
    ImageThing('ImageResults').hidden = true;
    SaveImageSetup();
    await PollImageRun(Generation);
  }
  catch (ErrorThing)
  {
    if (Generation === ImageGeneration)
      ImageStatus(ErrorThing.message);
  }
  finally
  {
    if (Generation === ImageGeneration)
    {
      ImageBusy = false;
      RefreshImageButtons();
    }
  }
});

async function PollImageRun(Generation = ImageGeneration)
{
  if (Generation !== ImageGeneration || !ImageRun)
    return;
  window.clearTimeout(ImagePollTimer);
  const RunId = ImageRun.id;
  try
  {
    const Latest = await ImageApi('/image-runs/' + RunId);
    // a late reply from the last run must not bring it back from the dead.
    if (Generation !== ImageGeneration || ImageRun?.id !== RunId)
      return;
    ImageRun = Latest;
    const Progress = ImageThing('ImageProgress');
    Progress.hidden = false;
    Progress.max = Math.max(1, ImageRun.total);
    Progress.value = ImageRun.completed;
    if (['running', 'cancelling'].includes(ImageRun.status))
    {
      ImageStatus((ImageRun.status === 'cancelling' ? 'Cancelling' : 'Measuring') + ': ' + ImageRun.completed + '/' + ImageRun.total + ' frames · ' + ImageRun.elapsed_seconds + ' s · ' + ImageRun.current_file);
      ImagePollTimer = window.setTimeout(() => PollImageRun(Generation), 1000);
    }
    else if (ImageRun.status === 'completed')
      ShowImageResults();
    else if (ImageRun.error)
      ImageStatus(ImageRun.error);
    RefreshImageButtons();
  }
  catch (ErrorThing)
  {
    if (Generation !== ImageGeneration || ImageRun?.id !== RunId)
      return;
    if ([400, 404].includes(ErrorThing.status))
    {
      ImageRun = null;
      PreviewThing = null;
      ImageThing('ImageResults').hidden = true;
      ImageStatus(ErrorThing.message);
    }
    else
    {
      ImageStatus('Connection interrupted: ' + ErrorThing.message + ' Refresh this tab to reconnect; completed tables remain on disk.');
      ImagePollTimer = window.setTimeout(() => PollImageRun(Generation), 4000);
    }
    RefreshImageButtons();
  }
}

ImageThing('CancelImages').addEventListener('click', async () =>
{
  const RunId = ImageRun?.id;
  const Generation = ++ImageGeneration;
  UploadStopThing?.abort();
  UploadStopThing = null;
  window.clearTimeout(ImagePollTimer);
  ImageBusy = true;
  RefreshImageButtons();
  try
  {
    if (!RunId)
      return ImageStatus('Upload cancelled.');
    const Cancelled = await ImageApi('/image-runs/' + RunId, {method:'DELETE'});
    if (Generation !== ImageGeneration || ImageRun?.id !== RunId)
      return;
    ImageRun = Cancelled;
    ImageStatus('Cancellation requested.');
    if (ImageRun.status === 'cancelling')
      await PollImageRun(Generation);
  }
  catch (ErrorThing)
  {
    if (Generation === ImageGeneration)
      ImageStatus(ErrorThing.message);
  }
  finally
  {
    if (Generation === ImageGeneration)
    {
      ImageBusy = false;
      RefreshImageButtons();
    }
  }
});

//MARK: the finished sheet
function ShowImageResults()
{
  const Result = ImageRun.result;
  ImageThing('ImageResults').hidden = false;
  ImageThing('ImageResultSummary').textContent = Result.usable_frames + '/' + Result.total_frames + ' usable measurements. Rejected frames remain in the CSV with a quality flag and blank flux.';
  ImageThing('ImageOutputPath').textContent = 'Saved to ' + Result.output_directory;
  ImageThing('ImageCsv').href = '/image-runs/' + ImageRun.id + '/lightcurve.csv';
  ImageThing('ImageMetadata').href = '/image-runs/' + ImageRun.id + '/metadata.json';
  ImageThing('ImageToFinder').disabled = Result.usable_frames < 2;
  ImageThing('ImageWarnings').replaceChildren();
  for (const Warning of Result.warnings)
  {
    const Item = document.createElement('li');
    Item.textContent = Warning;
    ImageThing('ImageWarnings').append(Item);
  }
  ImageThing('ImageRows').replaceChildren();
  for (const Row of Result.preview.slice(0, 200))
  {
    const Tr = document.createElement('tr');
    for (const Value of [Row.Time, Row.Flux, Row.flux_err, Row.quality ? (Row.qc_flags || 'Rejected') : 'Usable'])
    {
      const Td = document.createElement('td');
      Td.textContent = Value === null || Value === undefined ? '—' : String(Value);
      Tr.append(Td);
    }
    ImageThing('ImageRows').append(Tr);
  }
  DrawImageCurve(Result.preview);
  ImageStatus('Complete: ' + Result.usable_frames + '/' + Result.total_frames + ' usable frames. CSV and measurement metadata are saved.');
}

function DrawImageCurve(Rows)
{
  const Canvas = ImageThing('ImageCurveCanvas'), Pen = Canvas.getContext('2d');
  Pen.clearRect(0, 0, Canvas.width, Canvas.height);
  const Good = Rows.filter(Row => Row.quality === 0 && Number.isFinite(Row.Time) && Number.isFinite(Row.Flux));
  if (!Good.length)
    return;
  const Times = Good.map(Row => Row.Time), Flux = Good.map(Row => Row.Flux);
  const LowX = Math.min(...Times), HighX = Math.max(...Times);
  const LowY = Math.min(...Flux), HighY = Math.max(...Flux);
  const Pad = Math.max((HighY - LowY) * .15, .001);
  Pen.fillStyle = '#526173';
  Pen.font = '14px system-ui';
  Pen.fillText('Relative flux', 20, 22);
  Pen.fillText('Relative midpoint days: ' + LowX.toFixed(6) + ' – ' + HighX.toFixed(6), 20, Canvas.height - 10);
  Pen.fillText(LowY.toPrecision(6) + ' – ' + HighY.toPrecision(6), 20, 42);
  Pen.fillStyle = '#0f766e';
  for (const Row of Good)
  {
    const X = 60 + (Row.Time - LowX) / (HighX - LowX || 1) * (Canvas.width - 85);
    const Y = 45 + (HighY + Pad - Row.Flux) / (HighY - LowY + Pad * 2) * (Canvas.height - 90);
    Pen.beginPath();
    Pen.arc(X, Y, 3, 0, Math.PI * 2);
    Pen.fill();
  }
}

ImageThing('ImageToFinder').addEventListener('click', async () =>
{
  if (ImageBusy || ImageRun?.status !== 'completed' || !(ImageRun.result?.usable_frames >= 2))
    return;
  const RunId = ImageRun.id;
  ImageBusy = true;
  RefreshImageButtons();
  try
  {
    const Result = await PostImageJson('/image-runs/' + RunId + '/finder', {});
    if (window.parent !== window && typeof window.parent.OpenImageCurveFromImages === 'function')
      await window.parent.OpenImageCurveFromImages(Result.url);
    else
      window.location.href = Result.url;
  }
  catch (ErrorThing)
  {
    ImageStatus(ErrorThing.message);
  }
  finally
  {
    ImageBusy = false;
    RefreshImageButtons();
  }
});

//MARK: pick up a job after a refresh
(async function RestoreImageThing()
{
  const Generation = ImageGeneration;
  ImageBusy = true;
  DrawStarThingies();
  try
  {
    const Saved = JSON.parse(localStorage.getItem(ImageSaveKey) || 'null');
    if (!Saved || !/^[a-f0-9]{32}$/.test(Saved.id || ''))
      return;
    const Restored = await ImageApi('/image-runs/' + Saved.id);
    if (Generation !== ImageGeneration)
      return;
    ImageRun = Restored;
    const Options = Saved.options || {};
    StarThingies = Array.isArray(Options.stars) ? Options.stars : [];
    for (const [Key, Id] of Object.entries({radius:'ApertureRadius',inner:'SkyInner',outer:'SkyOuter',tracking:'TrackRadius',timestamp:'ImageClock',workers:'ImageWorkers'}))
      if (Options[Key] !== undefined)
        ImageThing(Id).value = Options[Key];
    if (ImageRun.science_count)
      await LoadImagePreview(Generation);
    await PollImageRun(Generation);
  }
  catch (ErrorThing)
  {
    if (Generation === ImageGeneration)
      ImageStatus(ErrorThing.message);
  }
  finally
  {
    if (Generation === ImageGeneration)
    {
      ImageBusy = false;
      RefreshImageButtons();
    }
  }
})();
